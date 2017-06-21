import json, urllib2, datetime
import chess, chess.uci, chess.svg
from ws4py.client.threadedclient import WebSocketClient

# chrome.exe --remote-debugging-port=9222

LICHESS_URL = 'https://lichess.org'
DEBUGGER_IP, DEBUGGER_PORT = '127.0.0.1', 9222
MOVETIME = 200 # milliseconds for engine to calculate
MOVETIME_FIRST = 20 # first calculation in milliseconds
ENGINE = ['stockfish'] # ['stockfish_8_x64'] ['houdini'] ['gnuchess', '--uci']
ENGINE_OPTIONS = {
#    'Threads': 2,
    'Ponder': True,
#    'Hash': 512, # MB
#    'Contempt': 100,
#    'UCI_Chess960': True,
}

class Lichess():
    def __init__(self, crdbg):
        self.crdbg = crdbg
        self.board = chess.Board()
        self.white = None
        self.my_last_move = None
        self.ply = 0

        self.engine = chess.uci.popen_engine(ENGINE)
        self.engine.uci()
        print self.engine.name
        print self.engine.author
        self.engine.setoption(ENGINE_OPTIONS)
        self.info_handler = chess.uci.InfoHandler()
        self.engine.info_handlers.append(self.info_handler)

        self.go = None
        self.best_moves = set()
        self.html = ''

    def tick(self, tick):
        if self.go and self.go.done() and self.white != None:
            best, ponder = self.go.result()
            move = str(best)
            if move not in self.best_moves:
                self.best_moves.add(move)
                score = self.info_handler.info['score'][1] if 1 in self.info_handler.info['score'] else chess.uci.Score(cp=None, mate=None)
                html = ''
                if (score.mate or score.cp):
                    html += 'Mate in %d moves' % score.mate if score.mate else 'Centipawn %d' % score.cp
                    html += chess.svg.board(self.board, flipped=bool(self.white == False), coordinates=False, lastmove=best, size=200)
                    self.html += html
                    self.crdbg.command('DOM.getDocument')
            self.go = self.engine.go(movetime=MOVETIME, async_callback=True)

    def sent(self, uci):
        self.my_last_move = uci

    def received(self, fen, ply, uci):
        self.engine.stop()

        white = bool(ply & 1) # True if ply is odd, False if even

        if ply < self.ply or ply > self.ply + 1: # new game detected
            self.board.reset()
            self.engine.ucinewgame()
            self.white = None
            self.my_last_move = None
        elif ply == self.ply: # lichess trys to be tricky
            return

        if uci == self.my_last_move:
            self.white = white
        self.ply = ply
        self.board.set_board_fen(fen)
        self.board.turn = not white
        self.engine.position(self.board)

        self.go = None
        self.best_moves = set()
        self.html = ''
        if uci != self.my_last_move and self.my_last_move:
            self.go = self.engine.go(movetime=MOVETIME_FIRST, async_callback=True)
        else:
            self.crdbg.command('DOM.getDocument')

class ChromeRemoteDebugger(WebSocketClient):
    def __init__(self, url, protocols=None, extensions=None, heartbeat_freq=None, ssl_options=None, headers=None):
        WebSocketClient.__init__(self, url, protocols, extensions, heartbeat_freq, ssl_options, headers)
        self.lichess = Lichess(self)
        self.last_tick = datetime.datetime.min
        self._next_id = 0
        self._request = {}

    def once(self):
        tick = datetime.datetime.utcnow()
        if self.last_tick < tick - datetime.timedelta(milliseconds=100):
            self.last_tick = tick
            self.lichess.tick(tick)
        return WebSocketClient.once(self)

    def opened(self):
        print 'ChromeRemoteDebugger connection opened'
        self.command('Network.enable')

    def closed(self, code, reason=None):
        print 'ChromeRemoteDebugger connection closed', code, reason

    def received_message(self, m):
        r = json.loads(str(m))
        if 'id' in r and 'result' in r:
            request = self._request[r['id']]
            del self._request[r['id']]
            self.command_result(request, r['result'])
        elif 'method' in r and 'params' in r:
            self.command_from_chrome(r['method'], r['params'])

    def command(self, method, params={}):
        new_id = self._next_id
        self._next_id = self._next_id+1 if self._next_id < 0xffff else 0
        data = {
            'id': new_id,
            'method': method,
            'params': params,
        }
        self._request[new_id] = data
        self.send(json.dumps(data))
        return new_id

    def command_result(self, request, result):
        if request['method'] == 'DOM.getDocument':
            self.command('DOM.querySelector', {
                'nodeId': result['root']['nodeId'],
                'selector': 'div.board_left>h1',
            })
        elif request['method'] == 'DOM.querySelector':
            html = '<h1>%s</h1>' % self.lichess.html
            self.command('DOM.setOuterHTML', {
                'nodeId': result['nodeId'],
                'outerHTML': html,
            })

    def command_from_chrome(self, method, params):
        if method.startswith('Network.webSocketFrame'):
            if 'response' in params and 'payloadData' in params['response']:
                payloadData = json.loads(params['response']['payloadData'])
                if type(payloadData) == dict:
                    if 't' in payloadData and payloadData['t'] == 'move' and 'd' in payloadData:
                        if method == 'Network.webSocketFrameSent':
                            """ Example
                            {u'method': u'Network.webSocketFrameSent',
                             u'params': {u'requestId': u'7084.4037',
                                         u'response': {u'mask': True,
                                                       u'opcode': 1.0,
                                                       u'payloadData': u'{"t":"move","d":{"u":"e2e4","b":1}}'},
                                         u'timestamp': 629468.369466}}
                            """
                            if 'u' in payloadData['d']:
                                uci = payloadData['d']['u']
                                self.lichess.sent(uci)
                        elif method == 'Network.webSocketFrameReceived':
                            """ Example
                            {u'method': u'Network.webSocketFrameReceived',
                             u'params': {u'requestId': u'7084.4037',
                                         u'response': {u'mask': False,
                                                       u'opcode': 1.0,
                                                       u'payloadData': u'{"v":1,"t":"move","d":{"uci":"e2e4"
                            ,"san":"e4","fen":"rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR","ply":1,"dests
                            ":{"e7":"e6e5","b8":"a6c6","f7":"f6f5","g7":"g6g5","b7":"b6b5","a7":"a6a5","c7":
                            "c6c5","h7":"h6h5","d7":"d6d5","g8":"f6h6"}}}'},
                                         u'timestamp': 629468.718}}
                            """
                            if 'fen' in payloadData['d'] and 'ply' in payloadData['d'] and 'uci' in payloadData['d']:
                                fen = payloadData['d']['fen']
                                ply = payloadData['d']['ply']
                                uci = payloadData['d']['uci']
                                self.lichess.received(fen, ply, uci)

def debugger_websocket_url():
    for tab in json.loads(urllib2.urlopen('http://%s:%d/json' % (DEBUGGER_IP, DEBUGGER_PORT)).read()):
        if tab['url'].startswith(LICHESS_URL):
            return tab['webSocketDebuggerUrl'] # will not exist if debugger already attached
    return None

def main():
    url = debugger_websocket_url()

    if not url:
        print '"%s" tab not found' % LICHESS_URL
        return

    try:
        ws = ChromeRemoteDebugger(url, protocols=['http-only', 'chat'])
        ws.connect()
        ws.run_forever()
    except KeyboardInterrupt:
        ws.close()

if __name__ == '__main__':
    main()
