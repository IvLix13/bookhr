# План устранения замечаний по логике кадровых событий

Документ описывает план работ по четырём замечаниям, найденным при анализе
логики кадровых событий (`Event`) в модулях `backend/app/services/events.py`,
`rule_engine.py`, `notifications.py` и `attention.py`.

> **Статус:** все четыре пункта реализованы в ветке
> `cursor/hr-events-plan-and-ui-animations-f192` (см. ниже раздел «Что сделано»).

---

## Замечание 1. Нет машины состояний событий

### Проблема

`transition_event_status()` меняет статус на любой запрошенный без проверки, что
переход допустим. Как следствие:

- можно «завершить» уже отменённое событие (`cancelled → completed`);
- `reopen` возвращает в `planned` даже завершённое событие, что легально по задумке,
  но нигде не отделено от недопустимых переходов;
- запись в `EventStatusHistory` создаётся даже для «пустых» переходов (`planned → planned`).

```15:44:backend/app/services/events.py
def transition_event_status(
    event: Event,
    new_status: EventStatus,
    comment: str | None = None,
) -> Event:
    old_status = event.status
    event.status = new_status.value
    ...
```

### Целевое поведение

Явная таблица допустимых переходов. Недопустимый переход поднимает доменное
исключение `InvalidEventTransition`, которое API преобразует в HTTP 409.

| Из \ В | planned | overdue | completed | cancelled |
|---|---|---|---|---|
| planned | — (no-op) | ✅ (авто) | ✅ | ✅ |
| overdue | ✅ (reopen/recalc) | — (no-op) | ✅ | ✅ |
| completed | ✅ (reopen, admin) | ❌ | — | ❌ |
| cancelled | ✅ (reopen, admin) | ❌ | ❌ | — |

### Шаги реализации

1. В `backend/app/services/events.py` добавить:
   - `class InvalidEventTransition(Exception)`;
   - словарь `ALLOWED_TRANSITIONS: dict[EventStatus, set[EventStatus]]`;
   - в начало `transition_event_status()` — проверку. Если `new_status == old_status`,
     возвращать событие без записи в историю (no-op). Если переход не в
     `ALLOWED_TRANSITIONS[old]` — бросать `InvalidEventTransition`.
2. Добавить параметр `force: bool = False` для служебных сценариев (миграции,
   `reopen` администратором), который обходит проверку, но всё равно пишет историю.
3. В `backend/app/api/events.py` (`complete_event`, `cancel_event`, `reopen_event`)
   обернуть вызовы в `try/except InvalidEventTransition` и возвращать
   `api_response(message=..., status=409)`.
4. Проверить вызовы в `rule_engine.py` (`cancel_stale_rule_events`,
   `_upsert_rule_event`): отмена уже завершённого события теперь невозможна, но код
   и так пропускает `COMPLETED/CANCELLED` (строки 40-41), поэтому регрессий нет.

### Тесты

- `backend/tests/test_events.py`: параметризованные кейсы всех переходов —
  допустимые проходят, недопустимые бросают `InvalidEventTransition`.
- Тест на no-op: `planned → planned` не создаёт запись в `EventStatusHistory`.
- API-тест: `POST /events/{id}/complete` на отменённом событии → 409.

### Риск

Низкий. Изменение локально в одной функции; основные вызовы rule engine уже
защищены проверкой статуса.

---

## Замечание 2. Дублирование формул `rule_key`

### Проблема

Формат `rule_key` задаётся в двух местах — в `process_*`-функциях (генерация) и в
`_expected_rule_keys()` (вычисление «ожидаемых» ключей для отмены устаревших).
Любое расхождение приведёт к тому, что актуальные события начнут ошибочно
отменяться `cancel_stale_rule_events()`.

```135:154:backend/app/services/rule_engine.py
    rule_key = f"contract-renewal-report:{contract.id}:{contract.end_date.isoformat()}"
```

```86:108:backend/app/services/rule_engine.py
        keys.add(
            f"contract-renewal-report:{contract.id}:{contract.end_date.isoformat()}"
        )
```

### Целевое поведение

Единственный источник истины для формул ключей. Формула и «ведущая дата» описаны
один раз и переиспользуются и при генерации, и при вычислении ожидаемых ключей.

### Шаги реализации

1. Ввести чистые функции формирования ключей в `rule_engine.py`:
   ```python
   def contract_rule_key(contract) -> str: ...
   def grade_rule_key(grade_history_id, eligible_date) -> str: ...
   def passport_rule_key(passport) -> str: ...
   ```
2. Заменить строковые литералы в `process_contract_rules`, `process_grade_rules`,
   `process_passport_rules` и в `_expected_rule_keys()` на вызовы этих функций.
3. Рассмотреть вынесение трёх правил в единый реестр
   `RULES: list[RuleSpec]`, где `RuleSpec` описывает: как найти сущность, как
   собрать `rule_key`, `title`, `event_type`, смещение даты (`offset_months`),
   `reference_type`. Тогда `recalculate_employment_events` и `_expected_rule_keys`
   становятся циклом по `RULES` и полностью исключают дублирование логики.
4. `find_contract_renewal_event()` — оставить, но использовать префикс из
   `contract_rule_key` через общую константу `CONTRACT_RULE_PREFIX`.

### Тесты

- `backend/tests/test_rule_engine.py`: тест-инвариант — для сотрудника с
  договором/грейдом/паспортом множество `rule_key` сгенерированных событий
  строго равно `_expected_rule_keys(employment)` (ни одно актуальное событие не
  попадает под отмену).
- Регресс: после повторного `run_rule_engine` `cancelled == 0` при неизменных данных.

### Риск

Средний. Меняется формирование ключей; при ошибке возможна массовая отмена/
пересоздание событий. Обязателен инвариант-тест из предыдущего пункта и прогон на
демо-данных (`flask seed-demo --force`).

---

## Замечание 3. Скрытая запись в БД на GET-запросах

### Проблема

`refresh_overdue_events()` переводит просроченные `planned`-события в `overdue` и
вызывается на каждый `GET /events`, `GET /events/upcoming` и при сборке «Внимание».
Функция не коммитит сама и полагается на коммит вызывающего кода, из-за чего:

- GET-эндпоинты неявно пишут в БД (побочный эффект на «чтении»);
- при отсутствии коммита в каком-то пути перевод в `overdue` теряется;
- под нагрузкой каждый список инициирует запись + запись истории на каждое событие.

```71:84:backend/app/services/events.py
def refresh_overdue_events(company_id: int | None = None) -> int:
    today = today_moscow()
    query = Event.query.filter(
        Event.status == EventStatus.PLANNED.value,
        Event.event_date < today,
    )
    ...
```

### Целевое поведение

Единый предсказуемый механизм: пересчёт `overdue` — это операция записи,
выполняемая фоновой командой и мутирующими эндпоинтами, а не GET-запросами.

### Варианты (выбрать один)

**Вариант A (рекомендуемый) — вычислять «эффективный статус» на чтении.**
- Не мутировать БД в GET. Добавить в сериализатор `event_to_dict` поле
  `effective_status`: если `status == planned` и `event_date < today` → `overdue`.
- Материализация в БД остаётся только за `flask run-rules` (фон) и мутирующими
  ручками (`create/complete/cancel`).
- Плюсы: GET становится чистым чтением; нет лишних записей и истории.
- Минусы: фильтр `status=overdue` в списке потребует учитывать «виртуальный»
  overdue (доработать SQL-условие: `status == overdue OR (status == planned AND date < today)`).

**Вариант B — оставить материализацию, но явно управлять транзакцией.**
- `refresh_overdue_events()` принимает `commit: bool = False`; GET-пути вызывают с
  `commit=True` в отдельной короткой транзакции до основного запроса чтения.
- Плюсы: минимальные изменения. Минусы: запись на GET сохраняется.

### Шаги реализации (Вариант A)

1. В `event_to_dict` (`backend/app/api/serializers.py`) добавить вычисление
   `effective_status` через `today_moscow()`.
2. Убрать вызовы `refresh_overdue_events()` из `list_events`, `upcoming_events`
   (`backend/app/api/events.py`) и из `_collect_event_items` (`attention.py`).
3. Обновить фильтрацию по статусу и выборку «просрочено»/«ближайшее», чтобы она
   учитывала виртуальный overdue.
4. Оставить материализацию в `run_rule_engine()` (там она уже есть, строка 244) —
   чтобы уведомления и отчётность видели «настоящий» статус.

### Тесты

- `test_events.py`: GET списка с просроченным `planned`-событием возвращает
  `effective_status == "overdue"` и при этом `SELECT` не меняет строки в БД
  (проверить, что `status` в БД остался `planned` до прогона `run-rules`).
- `test_attention.py`: просроченные события попадают в категорию `events` без
  побочной записи.

### Риск

Средний. Затрагивает контракты API (появляется `effective_status`) и фильтрацию.
Нужна синхронизация с фронтендом (`utils/statuses.ts`), но обратная совместимость
сохраняется — поле `status` остаётся.

---

## Замечание 4. Нет эскалации по просроченным событиям

### Проблема

Просроченные события продолжают слать те же уведомления с увеличенным интервалом
(`overdue_interval_days`), а завершённые пропускаются. Отдельного «эскалационного»
шага (уведомление ответственному/руководителю, повышение важности) нет.

```129:137:backend/app/services/notifications.py
            interval = rule.overdue_interval_days if rule else 3
            if event.status == EventStatus.OVERDUE.value and rule:
                interval = rule.overdue_interval_days
            elif rule:
                interval = rule.repeat_interval_days
```

### Целевое поведение

Настраиваемая эскалация: по достижении порога просрочки уведомление уходит в
эскалационный канал и/или повышается его важность.

### Шаги реализации

1. Модель `NotificationRule` (`backend/app/models/notification.py`): добавить поля
   - `escalation_room_token: str | None` — отдельный канал эскалации;
   - `escalation_after_days: int | None` — порог в днях просрочки;
   - миграция Alembic (`backend/migrations/versions/0004_notification_escalation.py`).
2. В `_build_message()` (`notifications.py`) добавить пометку для эскалации
   (например, префикс `⚠️ ПРОСРОЧЕНО N дн.:`), вычисляя дни просрочки от
   `event.event_date` до `today_moscow()`.
3. В `process_pending_notifications()` при `event.status == overdue` и
   `days_overdue >= rule.escalation_after_days` дублировать доставку в
   `escalation_room_token` (с собственным идемпотентным ключом
   `escalate:{event_id}:{rule_id}:{bucket}`, где bucket — номер порога).
4. Настройки правил уведомлений на фронтенде (`SettingsView.vue`): добавить поля
   канала и порога эскалации.

### Тесты

- `test_notifications` (при наличии) или новый файл: событие с просрочкой ≥ порога
  создаёт доставку в эскалационный канал ровно один раз (идемпотентность).
- Событие без просрочки/ниже порога эскалацию не создаёт.

### Риск

Средний. Требует миграции БД и изменения внешней интеграции (Nextcloud Talk).
Развёртывать после Замечания 3 (единый источник статуса `overdue`).

---

## Рекомендуемый порядок выполнения

1. **Замечание 1** (машина состояний) — изолированное, снижает класс ошибок.
2. **Замечание 2** (единый `rule_key`) — устраняет тихие баги отмены событий.
3. **Замечание 3** (overdue на чтении) — меняет контракт статуса, база для №4.
4. **Замечание 4** (эскалация) — строится поверх согласованного `overdue`.

## Общие требования к каждому PR

- Покрытие новыми юнит-тестами в `backend/tests/`.
- Прогон `cd backend && .venv/bin/pytest` — зелёный.
- Обновление затронутых сериализаторов и типов фронтенда (`frontend/src/types`,
  `frontend/src/utils/statuses.ts`) при изменении API-контракта.
- Обновление раздела «Кадровые события» в документации при изменении поведения.

---

## Что сделано

### 1. Машина состояний
- `InvalidEventTransition`, `ALLOWED_TRANSITIONS`, no-op при том же статусе,
  параметр `force` в `transition_event_status()`.
- API `complete` / `cancel` / `reopen` возвращают HTTP 409 при недопустимом переходе.
- Создание события пишет историю с `old_status=None` через `record_event_created()`.

### 2. Единый `rule_key`
- Функции `contract_rule_key` / `grade_rule_key` / `passport_rule_key` и префиксы
  `CONTRACT_RULE_PREFIX` и т. д.
- `process_*` и `_expected_rule_keys` используют одни и те же функции.
- Инвариант-тест: открытые rule-события ≡ `_expected_rule_keys(employment)`.

### 3. Overdue на чтении (вариант A)
- `effective_event_status()`, поле `effective_status` в `event_to_dict` и в
  `renewal_report_event`.
- GET `/events`, `/events/upcoming` и attention больше не вызывают
  `refresh_overdue_events()`; фильтр `status=overdue` учитывает виртуальный overdue.
- Материализация остаётся в `run_rule_engine()`.
- Фронтенд: `resolveEventStatus()`, отображение через `effective_status`.

### 4. Эскалация уведомлений
- Поля `escalation_room_token`, `escalation_after_days` + миграция
  `0004_notification_escalation`.
- `queue_escalation_for_event()` с идемпотентным ключом `escalate:{event}:{rule}:{bucket}`.
- Пометка в сообщении `⚠️ ПРОСРОЧЕНО N дн.:`.
- Настройки в `SettingsView.vue`.
