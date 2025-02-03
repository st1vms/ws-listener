# ws-reader

Python Websocket reader based off Selenium and Chromedriver.
Able to read inbound and outbound websocket messages in a browser session.

## Requirements

- Windows

- Python >= 3.10

- Latest Chrome version

- Latest stable [chromedriver.exe](https://googlechromelabs.github.io/chrome-for-testing/) inside a PATH folder

- `selenium` package installed

```shell
pip install selenium
```

## Example Usage

```py
# Import listener
from ws_reader import WSListener

# Create a listener
listener = WSListener(
    url='https://www.twitch.tv/',
    chrome_profile='Default', # Default chrome profile
    headless=True, # Defaults to headless
    logging=False # Disable message logging
)

# Run the listener into a daemon thread
try:
    listener.start()
    # Print first 10 messages and exit
    for _ in range(10):
        # Read WebSocketMessage from internal queue
        print(listener.messages.get())
finally:
    # Remember to close the listener thread
    listener.close()
```

## WebSocketMessage type

The internal `messages` Queue holds all the messages received and sent over the browser session,
they are dataclasses of type `WebSocketMessage`.

These are the properties of a message:

-`payload` (str): The content of the WebSocket message.

-`request_id` (str): A unique identifier for the request associated with the message.

-`timestamp` (float): The time at which the message was received, represented as a Unix timestamp.

-`url` (str): The URL of the WebSocket endpoint from which the message was received or sent to.
