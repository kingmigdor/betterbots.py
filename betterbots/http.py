"""
MIT License

Copyright (c) 2022-present KingMigDOR

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from http.client import HTTPException
import aiohttp
import asyncio
from dataclasses import MISSING
import logging
from urllib.parse import quote as _uriquote
from typing import (
    Any,
    ClassVar,
    Coroutine,
    Dict,
    Optional,
    Type,
    TypeVar,
    TYPE_CHECKING,
    Union,
)

from .gateway import BetterBotsWebSocketResponse

if TYPE_CHECKING:
    from types import TracebackType
    
    T = TypeVar('T')
    BE = TypeVar('BE', bound=BaseException)
    Response = Coroutine[Any, Any, T]

_log = logging.getLogger(__name__)


async def json_or_text(response: aiohttp.ClientResponse) -> Union[Dict[str, Any], str]:
    text = await response.text(encoding='utf-8')
    try:
        if response.headers['content-type'] == 'application/json':
            return await response.json()
    except KeyError:
        pass

    return text


class Route:
    BASE: ClassVar[str] = 'https://api.betterbots.gg'
    
    def __init__(self, method: str, path: str, **parameters: Any) -> None:
        self.path: str = path
        self.method: str = method
        url = self.BASE + self.path
        if parameters:
            url = url.format_map({k: _uriquote(v) if isinstance(v, str) else v for k, v in parameters.items()})
        self.url: str = url
            
        
class HTTPClient:
    """Represents an HTTP client sending HTTP requests to the BetterBots.gg API"""
    
    def __init__(
        self, 
        connector: Optional[aiohttp.BaseConnector] = None,
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.loop: asyncio.AbstractEventLoop = loop or asyncio.get_event_loop()
        self.connector = connector
        self.__session: aiohttp.ClientSession = MISSING
        self._global_over: asyncio.Event = asyncio.Event()
        self._global_over.set()
        self.token: Optional[str] = None
        
    def recreate(self) -> None:
        if self.__session.closed:
            self.__session = aiohttp.ClientSession(
                connector=self.connector, ws_response_class=BetterBotsWebSocketResponse
            )
        
    async def request(self, route: Route, **kwargs: Any) -> aiohttp.ClientResponse:
        _log.debug(f'Requesting {route.method} {route.url}')
        
        headers: Dict[str, str] = {}
        
        if self.token:
            headers['APIKey'] = self.token
            
        kwargs['headers'] = headers
        
        async with self.session.request(route.method, route.url, **kwargs) as response:
            _log.debug('%s %s with %s returned %s', route.method, route.url, kwargs.get('data'), response.status)
            data = await json_or_text(response)
            
            # success
            if 300 > response.status >= 200:
                return data
    
    async def ws_connect(self, url: str) -> Any:
        return await self.__session.ws_connect(url)
    
    async def close(self) -> None:
        if self.__session:
            await self.__session.close()
            
    async def static_login(self, token: str) -> None:
        self.__session = aiohttp.ClientSession(connector=self.connector, ws_response_class=BetterBotsWebSocketResponse)
        old_token = self.token
        self.token = token
        
        try:
            data = await self.request(Route('GET', '/me'))
        except HTTPException as e:
            self.token = old_token
            if e.status == 401:
                raise ValueError('Invalid token')
            raise
        
        return data