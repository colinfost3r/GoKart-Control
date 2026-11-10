"""Pure pairing-record corruption/parser checks; no keys or hardware access."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
class PairingTests(unittest.TestCase):
    def test_record_and_input_validation(self):
        source = r'''#include "PairingRecord.h"
#include <cassert>
#include <cstring>
int main(){
  using namespace m5now; Pairing p{},out{}; uint8_t b[PAIR_BYTES]{};
  assert(parseMac("02:12:34:56:78:9a",p.peer));
  assert(parseHex("0102030405060708090a0b0c0d0e0f10",p.lmk,16));
  assert(parseHex("101112131415161718191a1b1c1d1e1f",p.pmk,16));
  assert(encodePair(p,b,sizeof b));assert(decodePair(b,sizeof b,out));
  assert(!memcmp(p.peer,out.peer,6)&&!memcmp(p.lmk,out.lmk,16)&&!memcmp(p.pmk,out.pmk,16));
  for(size_t i=0;i<sizeof b;++i){b[i]^=1;assert(!decodePair(b,sizeof b,out));b[i]^=1;}
  for(size_t n=0;n<sizeof b;++n)assert(!decodePair(b,n,out));
  assert(!encodePair(p,b,sizeof b-1));
  assert(!parseMac("01:02:03:04:05:gg",out.peer));
  assert(!parseMac("01-02-03-04-05-06",out.peer));
  assert(!parseHex("00",out.lmk,16));assert(!parseHex("zz02030405060708090a0b0c0d0e0f10",out.lmk,16));
  p.peer[0]|=1;assert(!encodePair(p,b,sizeof b));p.peer[0]&=~1;
  memset(p.lmk,0,16);assert(!encodePair(p,b,sizeof b));
}
'''
        compiler=shutil.which('c++');self.assertIsNotNone(compiler)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(source)
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                '-I'+str(ROOT/'firmware/libraries/M5EspNowLink/src'),str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True,timeout=20)
if __name__=='__main__':unittest.main()
