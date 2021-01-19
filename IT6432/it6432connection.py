import socket
from time import time, sleep


class IT6432Connection:
    ##########  Connection parameters ##########
    IT6432_ADDRESS1 = "192.168.237.47"
    IT6432_ADDRESS2 = "192.168.237.48"
    IT6432_ADDRESS3 = "192.168.237.49"

    IT6432_PORT = 30000

    def __init__(self, channel: int):
        self.sock = socket.socket()
        self._channel = channel
        self.host = '0.0.0.0'
        self.port = 0
        
        self.connected = False
        
        self.read_termination = '\n'
        self._chunk_size = 1024

        self.connect()
        self.sock.recv(self._chunk_size)
        
        self._timeout = 5.0
        try:
            self.sock.settimeout(self._timeout)
        except Exception as exc:
            print(f'A problem occured while trying to set Timeout: {exc}')



    def connect(self) -> None:
        """Connects to the server (IP address and port number)"""
        try:
            if self._channel == 1:
                self.host = self.IT6432_ADDRESS1
            elif self._channel == 2:
                self.host = self.IT6432_ADDRESS2
            elif self._channel == 3:
                self.host = self.IT6432_ADDRESS3
            self.port = self.IT6432_PORT
            self.sock.connect((self.host, self.port))
            self.connected = True
            
            id_info = self._query('*IDN?')
            id_info_list = id_info.split(',')
            for line in id_info_list:
                print(line)
            
        except Exception as exc:
            print(f'A problem occured while trying to connect to channel {self._channel}: {exc}')

    def channel(self) -> int:
        """
        print the channel that this current source is
        """
        return self._channel


    def _write(self, cmd: str):
        """
        Writes command as string to the instrument
        If there is an error, an empty string is returned.
        """
        # add command termination
        cmd += self.read_termination
        try:
            self.sock.sendall(cmd.encode('ascii'))
        except (ConnectionResetError, ConnectionError, ConnectionRefusedError, ConnectionAbortedError):
            return ''
  
  
    def _read(self, chunk_size=None) -> str:
        """
        Reads message sent from the instrument from the connection

        Args:
            chunk_size (int, optional): expected chunk size to be received. Defaults to None.

        Returns:
            the decoded received message (a string)
        """
        term_char_detected = False
        read_len = 0
        chunk = bytes()
        _chunk_size = chunk_size if chunk_size is not None else self._chunk_size

        try:
            while True:
                to_read_len = _chunk_size - read_len
                if to_read_len <= 0:
                    break
                data = self.sock.recv(to_read_len)
                chunk += data
                read_len += len(data)				
                term_char = self.read_termination.encode()
                if term_char in data:
                    term_char_ix = data.index(term_char)
                    read_len = term_char_ix + 1
                    term_char_detected = True
                    break
                else:
                    pass

        except socket.timeout:
            print('Timeout occurred!')
            return ''

        if read_len < _chunk_size:
            # Less than required data arrived, no more available
            more_data_available = False
        else:
            # MaxCount data arrived, possibly more data available
            if self.read_termination is not None:
                more_data_available = not term_char_detected
            else:
                more_data_available = True

        res = chunk.decode('ascii').strip('\n')
        return res

    
    def _query(self, cmd: str) -> str:
        """
        query the current source with any command

        Args:
            cmd (str): [description]

        Returns:
            str: [description]
        """
        self._write(cmd)
        sleep(0.05)
        ans = self._read()
        return ans


    def close(self) -> None:
        """Closes the socket connection"""
        self.sock.close()
  
    # context manager
    def __enter__(self):
        if not self.connected:
            self.connect()
        return self

    def __exit__(self, type, value, traceback):
        if self.connected:
            self.sock.close()
            return not self.connected
        else:
            return isinstance(value, TypeError)