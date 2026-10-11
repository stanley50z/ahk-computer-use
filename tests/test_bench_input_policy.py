"""Scenario v4 allows any input route; the bench records which routes a script used instead of failing it."""

from bench.run import script_input_methods


def test_input_routes_are_recognised_for_the_report():
    assert script_input_methods('root.FindElement({Type:"Button", Name:"Six"}).Invoke()') == ['semantic action']
    assert script_input_methods('await sky.click({window, screenshotId: s.id, x, y});') == ['pointer']
    assert 'keyboard/text input' in script_input_methods('SendText "98765*432/1234*56/789+6543-4321="')
    assert 'keyboard/text input' in script_input_methods('await sky.type_text({window, text:"123"});')
    assert 'keyboard/text input' in script_input_methods("cua-driver press_key '{\"key\":\"1\"}'")
    assert 'direct field value' in script_input_methods('field.Value := "123"')
    assert script_input_methods('FileAppend "hello", "*"') == []
