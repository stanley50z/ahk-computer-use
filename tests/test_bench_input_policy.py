"""The benchmark accepts UI button activation, not keyboard/text or value injection."""

from bench.run import script_input_violations


def test_ui_clicks_and_semantic_button_invocation_are_allowed():
    assert script_input_violations('root.FindElement({Type:"Button", Name:"Six"}).Invoke()') == []
    assert script_input_violations('root.FindElement({AutomationId:id}).Click()') == []
    assert script_input_violations('await sky.click({window, element_index:12});') == []


def test_keyboard_and_field_value_injection_remain_disallowed():
    for script in ['Send "123"', 'SendText "123"', 'ControlSend("123", target)',
                   'field.Value := "123"', 'field.SetValue("123")',
                   'await sky.type_text({window, text:"123"});', 'await sky.press_key({window,key:"1"});']:
        assert script_input_violations(script), script
