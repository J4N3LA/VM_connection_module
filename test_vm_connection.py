import pytest
from vm_connection import SSHConnection, HostUnreachable, RebootNotify

@pytest.fixture
def class_object():
    return SSHConnection(
        user="user",
        host="host",
        port=22,
        key_path="/key/path",
        script_path_local="/local/path",
        script_path_remote="/remote/path",
        local_log_file="/path/to/logfile")


def test_connection(mocker,class_object):
    mocker.patch.object(class_object,"is_alive",return_value=True)

    mock_client = mocker.Mock()
    mocker.patch("paramiko.SSHClient",return_value=mock_client)

    success = class_object.connect(timeout=5)

    assert success == True
    mock_client.connect.assert_called_once()

def test_reconnect_success(mocker,class_object):
    mocker.patch.object(class_object,"connect",side_effect=[False,True])
    mocker.patch.object(class_object,"get_boot",return_value=None)

    result = class_object.reconnect(retries=2,delay=0)
    assert result == True