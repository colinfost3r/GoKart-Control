#include "ScreenLifecycle.h"
#include <cassert>
#include <cstdio>
using namespace m5dash;
int main(){
 StartupScreen s;assert(!s.visible(0));s.begin(100);assert(s.visible(5099));assert(!s.visible(5100));assert(!s.visible(100));
 s.begin(0xfffffff0U);assert(s.visible(20));assert(!s.visible(6000));
 PageHold p;p.begin(100);assert(!p.maintenance(280,20,1899));assert(p.maintenance(280,20,1900));assert(!p.maintenance(280,20,5000));
 p.begin(100);assert(!p.maintenance(40,220,1000));assert(!p.maintenance(280,20,3000));
 p.begin(0xfffffff0U);assert(!p.maintenance(280,20,20));assert(p.maintenance(280,20,2000));p.reset();assert(!p.maintenance(280,20,8000));
 puts("Nonblocking wrap-safe startup/page hold passed");
}
