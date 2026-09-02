import type { Component } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import {
  IconAward,
  IconCalendar,
  IconContract,
  IconEmployees,
  IconEvent,
  IconGrade,
  IconImport,
  IconPassport,
  IconSettings,
  IconStats,
} from '@/components/icons'
import IconCake from '@/components/icons/IconCake.vue'
import type { useAuthStore } from '@/stores/auth'
import { MODULE_LABELS } from '@/utils/labels'

import awardsBg from '@/assets/sidebar/awards.png'
import calendarBg from '@/assets/sidebar/calendar.png'
import contractsBg from '@/assets/sidebar/contracts.png'
import employeesBg from '@/assets/sidebar/employees.png'
import eventsBg from '@/assets/sidebar/events.png'
import gradesBg from '@/assets/sidebar/grades.png'
import importBg from '@/assets/sidebar/import.png'
import passportsBg from '@/assets/sidebar/passports.png'
import rewardsBg from '@/assets/sidebar/rewards.png'
import settingsBg from '@/assets/sidebar/settings.png'
import statisticsBg from '@/assets/sidebar/statistics.png'
import toggleBg from '@/assets/sidebar/toggle.png'

export type AuthStore = ReturnType<typeof useAuthStore>

export interface SidebarNavItemConfig {
  name: string | ((auth: AuthStore) => string)
  labelKey: keyof typeof MODULE_LABELS
  icon: Component
  /** PNG shown as button background when the sidebar is expanded. */
  background: string
  /** Optional PNG for the active route; falls back to `background`. */
  backgroundActive?: string
  isVisible?: (auth: AuthStore) => boolean
  isActive?: (route: RouteLocationNormalizedLoaded) => boolean
}

export const sidebarToggleBackground = toggleBg

export const sidebarNavItems: SidebarNavItemConfig[] = [
  {
    name: 'calendar',
    labelKey: 'calendar',
    icon: IconCalendar,
    background: calendarBg,
  },
  {
    name: 'events',
    labelKey: 'events',
    icon: IconEvent,
    background: eventsBg,
  },
  {
    name: 'employees',
    labelKey: 'employees',
    icon: IconEmployees,
    background: employeesBg,
  },
  {
    name: 'contracts',
    labelKey: 'contracts',
    icon: IconContract,
    background: contractsBg,
  },
  {
    name: 'grades',
    labelKey: 'grades',
    icon: IconGrade,
    background: gradesBg,
    isActive: (route) => route.name === 'grades' || route.name === 'grade-catalog',
  },
  {
    name: 'rewards',
    labelKey: 'rewards',
    icon: IconAward,
    background: rewardsBg,
  },
  {
    name: 'awards',
    labelKey: 'awards',
    icon: IconCake,
    background: awardsBg,
  },
  {
    name: 'passports',
    labelKey: 'passports',
    icon: IconPassport,
    background: passportsBg,
  },
  {
    name: 'import-employees',
    labelKey: 'import',
    icon: IconImport,
    background: importBg,
    isActive: (route) =>
      route.name === 'import-employees' || route.name === 'import-rewards',
  },
  {
    name: 'statistics',
    labelKey: 'statistics',
    icon: IconStats,
    background: statisticsBg,
  },
  {
    name: (auth) => (auth.isAdmin() ? 'settings-users' : 'settings-notifications'),
    labelKey: 'settings',
    icon: IconSettings,
    background: settingsBg,
    isVisible: (auth) => auth.canManageNotifications(),
    isActive: (route) => typeof route.name === 'string' && route.name.startsWith('settings'),
  },
]

export function resolveSidebarNavName(
  item: SidebarNavItemConfig,
  auth: AuthStore,
): string {
  return typeof item.name === 'function' ? item.name(auth) : item.name
}

export function isSidebarNavItemVisible(
  item: SidebarNavItemConfig,
  auth: AuthStore,
): boolean {
  return item.isVisible?.(auth) ?? true
}

export function isSidebarNavItemActive(
  item: SidebarNavItemConfig,
  route: RouteLocationNormalizedLoaded,
): boolean {
  if (item.isActive) return item.isActive(route)
  const name = typeof item.name === 'string' ? item.name : null
  return name != null && route.name === name
}
