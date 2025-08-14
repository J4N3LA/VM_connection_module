import pytest
from vm_connection import SSHConnection, HostUnreachable, RebootNotify
from datetime import datetime
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

def test_reconnect_failure_exact(mocker, class_object):
    mocker.patch.object(class_object, "connect", return_value=False)
    mocker.patch.object(class_object, "get_boot", return_value=None)

    with pytest.raises(HostUnreachable) as check_value:
        class_object.reconnect(retries=2, delay=0)

    assert "All reconnection attemtps failed" in str(check_value.value)


def test_execute(mocker,class_object):

    mocker.patch.object(class_object,"get_boot",return_value = None)
    mocker.patch.object(class_object, "execute_after_reconnect", return_value=None)

    mock_channel = mocker.Mock()
    mock_channel.recv_ready.side_effect = [True,False]
    mock_channel.recv.side_effect = [b'line1\nline2\nline3\nline4\n']
    mock_channel.exit_status_ready.side_effect = [False,True]
    mock_channel.recv_exit_status.return_value = 0

    mock_transport = mocker.Mock()
    mock_transport.open_session.return_value = mock_channel

    class_object.client = mocker.Mock()
    class_object.client.get_transport.return_value = mock_transport

    mock_data_stdout = []
    def mock_logging(line,f):
        mock_data_stdout.append(line)

    class_object.execute(mock_logging,timeout=5,f=None)

    assert "line1" in mock_data_stdout
    assert "line2" in mock_data_stdout
    assert "line3" in mock_data_stdout
    assert "line4" in mock_data_stdout


def test_command_exec_timeout(mocker,class_object):
    mocker.patch.object(class_object, "get_boot", return_value=None)
    mocker.patch.object(class_object, "execute_after_reconnect", return_value=None)

    mock_channel = mocker.Mock()
    mock_channel.recv_ready.return_value = False 
    mock_channel.exit_status_ready.return_value = False
    mock_channel.recv_exit_status.return_value = 0

    mock_transport = mocker.Mock()
    mock_transport.open_session.return_value = mock_channel

    class_object.client = mocker.Mock()
    class_object.client.get_transport.return_value = mock_transport

    mock_data_stdout = []
    def mock_logging(line, f):
        mock_data_stdout.append(line)

    result = class_object.execute(mock_logging, timeout=1, f=None)

    assert result == -5


def test_execute_network_drop(mocker, class_object):
    mocker.patch.object(class_object, "get_boot", return_value=None)

    execute_after_mock = mocker.patch.object(class_object, "execute_after_reconnect", return_value=None)

    mock_channel = mocker.Mock()
    def recv_ready_side_effect():
        raise Exception("Network dropped")  
    mock_channel.recv_ready.side_effect = recv_ready_side_effect

    mock_channel.exit_status_ready.return_value = False
    mock_channel.recv_exit_status.return_value = 0
    mock_channel.recv.return_value = b""

    mock_transport = mocker.Mock()
    mock_transport.open_session.return_value = mock_channel

    class_object.client = mocker.Mock()
    class_object.client.get_transport.return_value = mock_transport

    mock_data_stdout = []
    def mock_logging(line, f):
        mock_data_stdout.append(line)

    class_object.execute(mock_logging, timeout=1, f=None)

    assert execute_after_mock.called


def test_reboot_notify_exception(mocker, class_object):
    class_object.boot_before = datetime.strptime("2025-08-13 10:00:00", "%Y-%m-%d %H:%M:%S")
    class_object.boot_after  = datetime.strptime("2026-08-13 10:00:00", "%Y-%m-%d %H:%M:%S")

    mock_channel = mocker.Mock()
    mock_channel.recv_ready.return_value = False
    mock_channel.exit_status_ready.return_value = False
    mock_channel.recv_exit_status.return_value = 0

    mock_transport = mocker.Mock()
    mock_transport.open_session.return_value = mock_channel

    class_object.client = mocker.Mock()
    class_object.client.get_transport.return_value = mock_transport

    mock_data_stdout = []
    def mock_logging(line, f):
        mock_data_stdout.append(line)

    mocker.patch.object(class_object, "reconnect", return_value=True)

    with pytest.raises(RebootNotify):
        class_object.execute_after_reconnect(mock_logging, timeout=5, f=None)
