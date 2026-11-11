from eltorpedo.claw import ClawStatus, config_errors, parse_statustext


def test_parse_movement_states():
    status = ClawStatus()
    assert parse_statustext("Claw: closing", status)
    assert status.state == "CLOSING"
    assert parse_statustext("Claw: object grasped, holding", status)
    assert status.state == "HOLDING"
    assert parse_statustext("Claw: fully open", status)
    assert status.state == "OPEN"


def test_parse_fault_keeps_reason():
    status = ClawStatus()
    assert parse_statustext("Claw: fault - overcurrent while holding", status)
    assert status.state == "FAULT"
    assert status.fault is True
    assert status.detail == "overcurrent while holding"


def test_parse_unavailable():
    status = ClawStatus()
    assert parse_statustext("Claw: INA219 not found", status)
    assert status.state == "UNAVAILABLE"
    assert status.unavailable is True


def test_ignores_non_claw_text():
    status = ClawStatus()
    assert parse_statustext("EKF3 IMU0 is using GPS", status) is False
    assert status.state == "UNKNOWN"


def test_config_errors_reports_missing_and_mismatch():
    required = {"GRIP_ENABLE": 1, "GRIP_TYPE": 3, "BTN0_FUNCTION": 140}
    errors = config_errors({"GRIP_ENABLE": 0, "GRIP_TYPE": 3}, required)
    assert "GRIP_ENABLE=0, need 1" in errors
    assert "BTN0_FUNCTION not read" in errors


def test_config_errors_empty_when_correct():
    required = {"GRIP_ENABLE": 1, "GRIP_TYPE": 3}
    assert config_errors({"GRIP_ENABLE": 1.0, "GRIP_TYPE": 3.0}, required) == []
