import paramiko
import os

class SSHConnection:
    def __init__(self,host,port, user, key_path):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = key_path

    def connect(self):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname=self.host,port=self.port,username=self.user,key_filename=self.key_path)

        while True:
            try:
                cmd = input(">>> ")
                if cmd == "exit": break
                else:
                    stdin,stdout,stderr = client.exec_command(cmd, get_pty=True)
                    print(stdout.read().decode())
                    print(stderr.read().decode())
            except KeyboardInterrupt:
                break
        

        client.close()


conn = SSHConnection(
                    host="127.0.0.1",
                    port=22,
                    user="njanelidze",
                    key_path="/home/njanelidze/.ssh/id_ed25519"
                    )

conn.connect()


