"""WebSocket listener using selenium and chromedriver"""

from os import path as ospath
from os import environ
from dataclasses import dataclass
from json import loads as json_loads
from queue import Queue
from threading import Event, Thread
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


CHROME_USER_DATA_DIR = ospath.join(environ["LOCALAPPDATA"], r"Google\Chrome\User Data")


@dataclass(frozen=True)
class WebSocketMessage:
    """
    A dataclass that represents a message received over a WebSocket connection.\n
    Attributes:
        `payload` (str): The content of the WebSocket message.
        `request_id` (str): A unique identifier for the request associated with the message.
        `timestamp` (float): The time at which the message was received, represented as a Unix timestamp.
        `url` (str): The URL of the WebSocket endpoint from which the message was received or sent to.
        `received` (bool): Flag indicating if the packet was received (True) or sent (False).
    """

    payload: str
    request_id: str
    timestamp: float
    url: str
    received: bool


class WSListener:
    """WebSocket listener class"""

    def __init__(
        self,
        url: str,
        chrome_profile: str = "Default",
        headless: bool = True,
        queue: Queue[WebSocketMessage] = None,
        logging: bool = False,
    ) -> None:
        """
        Initializes the WebSocket listener with the given parameters.\n
        Args:
            `url` (str): The website URL to open.
            `chrome_profile` (str, optional): The Chrome profile to use. Defaults to "Default".
            `headless` (bool, optional): Enable or disable browser headless mode, Defaults to True
            `queue` (Queue, optional): Optional Queue instance to use instead of internal one
            `logging` (bool, optional): Enable or disable message logging. Defaults to False.

        This listener provides a Queue property called `messages`, which will contain all the
        intercepted websocket messages, you can retrieve them with Queue methods like .get(),
        they will be dataclasses of type WebSocketMessage.
        """
        self.url = url
        self.logging = logging

        self.messages: Queue[WebSocketMessage] = queue or Queue()

        self.driver: webdriver.Chrome = None

        # Set Chrome options
        self.opts = Options()
        self.opts.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        self.opts.add_argument(f"--profile-directory={chrome_profile}")
        if headless:
            self.opts.add_argument("--headless")

        # Enable performance logging so that we can capture DevTools protocol events.
        self.opts.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        self.running: Event = Event()
        self.thread: Thread = None

        self.websocket_url_map = {}

    def _read_loop(self) -> None:
        """Reads in loop websocket for messages and calls the assigned callback
        to this listener, passing the message as argument"""

        while self.running.is_set():

            # Retrieve performance logs. Each log entry is a JSON string containing a CDP event.
            logs = self.driver.get_log("performance")

            # Process logs to find WebSocket frame events.
            for entry in logs:
                message = json_loads(entry["message"])["message"]
                method = message.get("method", "")
                params = message.get("params", {})

                # Capture the creation of a WebSocket connection.
                if method == "Network.webSocketCreated":
                    request_id = params.get("requestId")
                    ws_url = params.get("url")
                    if request_id and ws_url:
                        self.websocket_url_map[request_id] = ws_url

                        if self.logging:
                            print(
                                f"WebSocket created: [ID: {request_id}] URL: {ws_url}"
                            )

                # Process incoming WebSocket messages.
                elif method == "Network.webSocketFrameReceived":
                    request_id = params.get("requestId")
                    payload = message["params"]["response"].get("payloadData", "")
                    timestamp = message["params"].get("timestamp")
                    ws_url = self.websocket_url_map.get(request_id, "Unknown URL")
                    self.messages.put(
                        WebSocketMessage(
                            payload, request_id, timestamp, ws_url, received=True
                        )
                    )

                    if self.logging:
                        print(f"[Received @ {timestamp}] From {ws_url} : {payload}")
                # Process outgoing WebSocket messages.
                elif method == "Network.webSocketFrameSent":
                    request_id = params.get("requestId")
                    payload = message["params"]["response"].get("payloadData", "")
                    timestamp = message["params"].get("timestamp")
                    ws_url = self.websocket_url_map.get(request_id, "Unknown URL")
                    self.messages.put(
                        WebSocketMessage(
                            payload, request_id, timestamp, ws_url, received=False
                        )
                    )

                    if self.logging:
                        print(f"[Sent @ {timestamp}] To {ws_url} : {payload}")

    def close(self) -> None:
        """Wait for listener thread to close gracefully"""
        self.running.clear()
        self.thread.join()

    def __thread_task(self) -> None:
        self.driver = webdriver.Chrome(options=self.opts)

        try:
            # Enable the Network domain (this tells Chrome to start sending network events)
            self.driver.execute_cdp_cmd("Network.enable", {})

            self.driver.get(self.url)

            self._read_loop()
        finally:
            self.driver.quit()
            self.running.clear()

    def start(self) -> None:
        """Starts daemon thread that listens to websocket connection"""

        if self.running.is_set():
            raise RuntimeError("Listener is already running...")

        self.running.set()

        # Spawn daemon thread
        self.thread = Thread(name="WSListener", target=self.__thread_task, daemon=True)
        self.thread.start()
