import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StatusBadge from '@/components/StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders label and variant class', () => {
    const wrapper = mount(StatusBadge, {
      props: {
        label: 'Просрочено',
        variant: 'danger',
      },
    })

    expect(wrapper.text()).toContain('Просрочено')
    expect(wrapper.find('.badge.danger').exists()).toBe(true)
  })
})
