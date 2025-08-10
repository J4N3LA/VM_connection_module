import paramiko
import os
import time
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

        
    def execute(self,log_output_line,timeout):
        transport_name = self.client.get_transport()
        channel = transport_name.open_session()
        channel.get_pty()
        channel.exec_command("for i in {0..3};do echo hello $((i+1)) && sleep 0.5 ;done\n ls -l /root\nfor i in {0..5};do echo hello $((i+1)) && sleep 0.5 ;done")
        # channel.exec_command("for i in {0..5};do echo hello $((i+1)) && sleep 0.5 ;done")
        # channel.exec_command("sleep 10")

        last_activity  = time.time()
        data_stdout = ""
        data_stderr = ""

        while True:
            while channel.recv_ready():
                data_stdout += channel.recv(1024).decode()
                while "\n" in data_stdout:
                    line, data_stdout = data_stdout.split("\n",1)
                    # if line.strip():
                    #     log_output_line(line)
                    log_output_line(line)

                    last_activity = time.time()
                

            while channel.recv_stderr_ready():
                data_stderr += channel.recv_stderr(1024).decode()
                while "\n" in data_stderr:
                    line, data_stderr = data_stderr.split("\n",1)
                    # if line.strip():
                    #     log_output_line(line)
                    log_output_line(line)

                    last_activity = time.time()

            
            
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                break

            if time.time() - last_activity >= timeout:
                print("Time exceeded. exiting...")
                break

            time.sleep(0.1)
        
        self.client.close()
        return channel.recv_exit_status()




    def close(self):
        self.client.close()
        
    
def log_output_line(line):
    print(f"[REMOTE]>> {line.strip()}")

    

            
        

        


conn = SSHConnection(
                    host="127.0.0.1",
                    port=22,
                    user="njanelidze",
                    key_path="/home/njanelidze/.ssh/id_ed25519"
                    )

conn.connect()

exit_code = conn.execute(log_output_line,2)
print(exit_code)
conn.close()


