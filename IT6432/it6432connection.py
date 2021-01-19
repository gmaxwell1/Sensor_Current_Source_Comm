import socket
from time import time, sleep
# from qs3.utils import logger

class ErrorBase(Exception):
    def __init__(self, code, *args, **kwargs):
        self.code = code
        keys = kwargs.keys()
        if 'msg' in keys:
            self.msg = kwargs['msg']
        super().__init__(*args)


class GenericError(ErrorBase):
    def __init__(self, code, msg, *args, **kwargs):
        ErrorBase.__init__(self, code, *args, msg=msg, **kwargs)
        # logger.debug(f'{code}: {msg}')
        print(f'{code}: {msg}')
class ParameterOverflow(ErrorBase): pass
class InvalidCommand(ErrorBase): pass
class ExecutionError(ErrorBase): pass
class ErrorQueueOverrun(ErrorBase): pass
class SyntaxErrorSCPI(ErrorBase): pass
class InvalidCharacter(ErrorBase): pass
class StringDataError(ErrorBase): pass


class IT6432Connection:
    """
    Quick and dirty protocol for communication with IT 6432 current sources.
    The IP address/source port can be changed by reprogramming, although there
    should be no need to do this.
    """
    
    ##########  Connection parameters ##########
    IT6432_ADDRESS1 = "192.168.237.47"
    IT6432_ADDRESS2 = "192.168.237.48"
    IT6432_ADDRESS3 = "192.168.237.49"
    # default port nr.
    IT6432_PORT = 30000
    
    @staticmethod
    def _ErrorFactory(code, msg=''):
        errorClasses = {
            120: ParameterOverflow,
            170: InvalidCommand,
            -101: InvalidCharacter,
            -102: SyntaxErrorSCPI,
            -150: StringDataError,
            -200: ExecutionError,
            -350: ErrorQueueOverrun
        }
        
        errorClass = None
        if code in errorClasses.keys():
            errorClass = errorClasses[code]
            return errorClass(code)
        
        else:
            return GenericError(code, msg)
    
    def __init__(self, channel: int):
        """
        create an IT6432 object

        Args:
            channel (int): Only use channels 1,2,3
        """
        self.sock = socket.socket()
        self._channel = channel
        self.host = '0.0.0.0'
        self.port = 0
        self.connected = False
        
        self.read_termination = '\n'
        self._chunk_size = 1024
        
        self._timeout = 5.0
    

    def connect(self) -> None:
        """
        Connects to the server, i.e. the device
        """
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

            id_info = self.query('*IDN?')
            print(id_info.strip('\n'))
            
            self.sock.settimeout(self._timeout)
            
        except Exception as exc:
            # logger.debug(f'A problem occured while trying to connect to channel {self._channel}: {exc}')
            print(f'A problem occured while trying to connect to channel {self._channel}: {exc}')


    def channel(self) -> int:
        """
        print the channel that this current source is
        """
        return self._channel


    def _write(self, cmd: str, checkError=True):
        """
        Writes command as string to the instrument
        If there is an error, an empty string is returned.
        """
        # add command termination
        cmd += self.read_termination
        try:
            self.sock.sendall(cmd.encode('ascii'))
        except (ConnectionResetError, ConnectionError, ConnectionRefusedError, ConnectionAbortedError):
            # logger.debug(f'{__name__} error when sending the "{cmd}" command')
            print(f'{__name__} error when sending the "{cmd}" command')
        
        if checkError:
            self.checkError()
  
  
    def _read(self, chunk_size=None) -> str:
        """
        Reads message sent from the instrument from the connection. One chunk (1024 bytes) at
        a time.

        Args:
            chunk_size (int, optional): expected chunk size to be received. Defaults to None.

        Returns:
            str: the decoded received message
            bool: whether there is more data to be read
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
            # logger.debug(f'{__name__} Timeout occurred!')
            print(f'{__name__} Timeout occurred! on {self._channel}')
            return ''
        
        try:
            res = chunk.decode('ascii').strip('\n')
        except UnicodeDecodeError:
            res = chunk.decode('uft8').strip('\n')
            # logger.debug(f'{__name__} Non-ascii string received: {res}')
            print(f'{__name__} Non-ascii string received: {res}')
            
        return res

    
    def query(self, cmd: str, checkError=True) -> str:
        """
        query the current source with any command

        Args:
            cmd (str): an SCPI command

        Returns:
            str: the answer from the device
        """
        # more = False
        result = None
        self._write(cmd, checkError=False)
        sleep(0.1)
        result = self._read()
        if checkError:
            self.checkError()
            
        return result


    def checkError(self):
        error_code, error_message = self.query('system:error?', checkError=False).split(',')
        if int(error_code) != 0:
            try:
                raise self._ErrorFactory(int(error_code), error_message)
            except KeyError as e:
                raise RuntimeError(f'Unknown error code: {error_code}') from e


    def close(self) -> None:
        """
        Closes the socket connection
        """
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