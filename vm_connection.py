import paramiko
import os

class SSHConnection:
    def __init__(self,host,port, user, key_path):
        self.host = host
        self.port = port
        self.user = user
        self.key_path = key_path

    def connect(self):
        print(f"Trying to connect to {self.host}:{self.port}...")
        try:
            self.client = paramiko.SSHClient()
            self.client.load_system_host_keys()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(hostname=self.host,port=self.port,username=self.user,key_filename=self.key_path)
            print("Connection successfull")
        except Exception as e:
            print(f"Failed to connect\nError:{e}")
            exit

        
    def execute(self,callback):
        transport_name = self.client.get_transport()
        channel = transport_name.open_session()
        channel.get_pty()
        channel.exec_command("for i in {0..4};do echo hello $((i+1)) && sleep 1 ;done\n ls -l /root")
        # channel.exec_command("ls /root")
    

        
        data = ''

        while True:
            data = channel.recv(1024).decode()

            callback(data)

            if channel.exit_status_ready():break

        while True:
            data = channel.recv_stderr(1024).decode()
            callback(data)
            if channel.exit_status_ready():break



    def close(self):
        self.client.close()
        
    
def output(line):
    print(line)

            
        

        


conn = SSHConnection(
                    host="127.0.0.1",
                    port=22,
                    user="njanelidze",
                    key_path="/home/njanelidze/.ssh/id_ed25519"
                    )

conn.connect()
conn.execute(output)
conn.close()


