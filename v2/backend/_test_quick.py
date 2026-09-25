import sys
sys.path.insert(0, '.')
from app.services.parser import POCSAGParser, parse_line

# Test parse_line numeric
line = "POCSAG1200: Address: 9876543 Function: 2 Numeric: 1234567890"
result = parse_line(line)
assert result is not None
assert result["ric"] == "9876543"
assert result["func"] == "2"
assert result["message"] == "1234567890"
print("parse_line numeric OK")

# Test POCSAGParser single
parser = POCSAGParser()
parser.feed("POCSAG1200: Address: 1111111 Function: 1 Alpha: HELLO")
result = parser.feed("POCSAG1200: Alpha: WORLD")
assert result is None
result = parser.flush()
assert result is not None
assert result["ric"] == "1111111"
assert result["message"] == "HELLO WORLD"
print("POCSAGParser multiline OK")

# Test numeric parsing with parser
parser2 = POCSAGParser()
parser2.feed("POCSAG512: Address: 1234567 Function: 3 Numeric: 123")
# numeric continuation not captured (no match)
parser2.feed("POCSAG512: Numeric: 456")
# next header triggers flush
parser2.feed("POCSAG512: Address: 7654321 Function: 1 Alpha: NEXT")
msg = parser2.flush()  # should be second message
if msg:
    print(f"Parsed: {msg}")
print("All basic parser tests passed")