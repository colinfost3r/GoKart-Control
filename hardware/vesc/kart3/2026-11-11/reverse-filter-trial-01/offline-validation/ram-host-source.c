/*
    Copyright 2018, 2020, 2023 Joel Svensson   svenssonjoel@yahoo.se

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#define _POSIX_C_SOURCE 200809L
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <ctype.h>
#include <getopt.h>
#include <pthread.h>
#include <sys/time.h>
#include <unistd.h>

#include "lispbm.h"
#include "extensions/array_extensions.h"
#include "extensions/math_extensions.h"
#include "extensions/string_extensions.h"
#include "extensions/runtime_extensions.h"
#include "extensions/matvec_extensions.h"
#include "extensions/random_extensions.h"
#include "extensions/loop_extensions.h"
#include "lbm_channel.h"
#include "lbm_flat_value.h"

#define WAIT_TIMEOUT 2500

#define EVAL_CPS_STACK_SIZE 256
#define GC_STACK_SIZE 160
#define PRINT_STACK_SIZE 128
#define EXTENSION_STORAGE_SIZE 256
#define VARIABLE_STORAGE_SIZE 64

lbm_uint gc_stack_storage[GC_STACK_SIZE];
lbm_uint print_stack_storage[PRINT_STACK_SIZE];
extension_fptr extension_storage[EXTENSION_STORAGE_SIZE];
lbm_value variable_storage[VARIABLE_STORAGE_SIZE];

/* Tokenizer state for strings */
//static lbm_tokenizer_string_state_t string_tok_state;

/* Tokenizer statefor compressed data */
//static tokenizer_compressed_state_t comp_tok_state;

/* shared tokenizer */
//static lbm_tokenizer_char_stream_t string_tok;

static lbm_char_channel_t string_tok;
static lbm_string_channel_state_t string_tok_state;
static lbm_buffered_channel_state_t buffered_tok_state;

void *eval_thd_wrapper(void *v) {
  (void)v;
  lbm_run_eval();
  return NULL;
}

uint32_t timestamp_callback() {
  struct timeval tv;
  gettimeofday(&tv,NULL);
  return (uint32_t)(tv.tv_sec * 1000000 + tv.tv_usec);
}

void sleep_callback(uint32_t us) {
  struct timespec s;
  struct timespec r;
  s.tv_sec = 0;
  s.tv_nsec = (long)us * 1000;
  nanosleep(&s, &r);
}
volatile bool experiment_success = false;
volatile bool experiment_done = false;

lbm_cid test_cid = -1;

static bool command_failed=false;
void context_done_callback(eval_context_t *ctx) {
 char result[256]; lbm_print_value(result,sizeof(result),ctx->r);
 printf("RESULT %s\n",result); fflush(stdout);
 if(lbm_is_error(ctx->r)) command_failed=true;
 experiment_done=true;
}

bool dyn_load(const char *str, const char **code) {

  size_t len = strlen(str);
  bool res = false;
  if (len == 5 && strncmp(str, "defun", 5) == 0) {
    *code = "(define defun (macro (name args body) `(define ,name (lambda ,args ,body))))";
    res = true;
  }  else if (len == 4 && strncmp(str, "iota", 4) == 0) {
    *code = "(define iota (lambda (n)"
            "(range 0 n)))";
    res = true;
  } else if (len == 4 && strncmp(str, "take", 4) == 0) {
    *code = "(define take (lambda (n xs)"
            "(let ((take-tail (lambda (acc n xs)"
            "(if (= n 0) acc"
            "(take-tail (cons (car xs) acc) (- n 1) (cdr xs))))))"
            "(reverse (take-tail nil n xs)))))";
    res = true;
  } else if (len == 4 && strncmp(str, "drop", 4) == 0) {
    *code = "(define drop (lambda (n xs)"
            "(if (= n 0) xs"
            "(if (eq xs nil) nil"
            "(drop (- n 1) (cdr xs))))))";
    res = true;
  } else if (len == 3 && strncmp(str, "zip", 3) == 0) {
    *code = "(define zip (lambda (xs ys)"
            "(if (eq xs nil) nil"
            "(if (eq ys nil) nil"
            "(cons (cons (car xs) (car ys)) (zip (cdr xs) (cdr ys)))))))";
    res = true;
  } else if (len == 6 && strncmp(str, "lookup", 6) == 0) {
    *code = "(define lookup (lambda (x xs)"
            "(if (eq xs nil) nil"
            "(if (eq (car (car xs)) x)"
            "(car (cdr (car xs)))"
            "(lookup x (cdr xs))))))";
    res = true;
  } else if (len == 5 && strncmp(str, "foldr", 5) == 0) {
    *code = "(define foldr (lambda (f i xs)"
            "(if (eq xs nil) i"
            "(f (car xs) (foldr f i (cdr xs))))))";
    res = true;
  } else if (len == 5 && strncmp(str, "foldl", 5) == 0) {
    *code = "(define foldl (lambda (f i xs)"
            "(if (eq xs nil) i (foldl f (f i (car xs)) (cdr xs)))))";
    res = true;
  }


  for (unsigned int i = 0; i < (sizeof(loop_extensions_dyn_load) / sizeof(loop_extensions_dyn_load[0])); i ++) {
    if (strncmp (str, loop_extensions_dyn_load[i]+8, len)  == 0) {
      *code = loop_extensions_dyn_load[i];
      res = true;
      break;
    }
  }

  return res;
}

  //lbm_value ext_even(lbm_value *args, lbm_uint argn) {
LBM_EXTENSION(ext_even, args, argn){
  if (argn < 1) return lbm_enc_sym(SYM_NIL);

  lbm_value v = args[0];

  if (lbm_type_of(v) == LBM_TYPE_I ||
      lbm_type_of(v) == LBM_TYPE_U) {
    if (lbm_dec_i(v) % 2 == 0)
      return lbm_enc_sym(SYM_TRUE);
  }

  return lbm_enc_sym(SYM_NIL);
}

LBM_EXTENSION(ext_odd, args, argn){
  //lbm_value ext_odd(lbm_value *args, lbm_uint argn) {

  if (argn < 1) return lbm_enc_sym(SYM_NIL);

  lbm_value v = args[0];

  if (lbm_type_of(v) == LBM_TYPE_I ||
      lbm_type_of(v) == LBM_TYPE_U) {
    if (lbm_dec_i(v) % 2 == 1)
      return lbm_enc_sym(SYM_TRUE);
  }

  return lbm_enc_sym(SYM_NIL);
}

LBM_EXTENSION(ext_numbers, args, argn) {

  bool b = true;

  for (unsigned int i = 0; i < argn; i ++) {
    if (!lbm_is_number(args[i])) {
      b = false;
      break;
    }
  }
  return lbm_enc_sym(b ? SYM_TRUE : SYM_NIL);
}


LBM_EXTENSION(ext_event_sym, args, argn) {
  lbm_value res = ENC_SYM_EERROR;
  if (argn == 1 && lbm_is_symbol(args[0])) {
    lbm_flat_value_t v;
    if (lbm_start_flatten(&v, 1 + sizeof(lbm_uint))) {
      f_sym(&v, lbm_dec_sym(args[0]));
      lbm_finish_flatten(&v);
      lbm_event(&v);
      res = ENC_SYM_TRUE;
    }
  }
  return res;
}

LBM_EXTENSION(ext_event_float, args, argn) {
  lbm_value res = ENC_SYM_EERROR;
  if (argn == 1 && lbm_is_number(args[0])) {
    float f = lbm_dec_as_float(args[0]);
    lbm_flat_value_t v;
    if (lbm_start_flatten(&v, 1 + sizeof(float))) {
      f_float(&v, f);
      lbm_finish_flatten(&v);
      lbm_event(&v);
      res = ENC_SYM_TRUE;
    }
  }
  return res;
}

LBM_EXTENSION(ext_event_list_of_float, args, argn) {
  LBM_CHECK_NUMBER_ALL();
  lbm_value res = ENC_SYM_EERROR;
  if (argn >= 2) {
    lbm_flat_value_t v;
    if (lbm_start_flatten(&v, 8 + ((1 + sizeof(lbm_uint) * argn) + (1 + sizeof(lbm_uint))))) {
      for (int i = 0; i < argn; i ++) {
        f_cons(&v);
        float f = lbm_dec_as_float(args[i]);
        f_float(&v, f);
      }
      f_sym(&v, SYM_NIL);
      lbm_finish_flatten(&v);
      lbm_event(&v);
      res = ENC_SYM_TRUE;
    }
  }
  return res;
}

LBM_EXTENSION(ext_event_array, args, argn) {
  lbm_value res = ENC_SYM_EERROR;
  if (argn == 1 && lbm_is_symbol(args[0])) {
    char *hello = "hello world";
    lbm_flat_value_t v;
    if (lbm_start_flatten(&v, 100)) {
      f_cons(&v);
      f_sym(&v,lbm_dec_sym(args[0]));
      f_lbm_array(&v, 12, LBM_TYPE_CHAR, (uint8_t*)hello);
      lbm_finish_flatten(&v);
      lbm_event(&v);
      res = ENC_SYM_TRUE;
    }
  }
  return res;
}

LBM_EXTENSION(ext_block, args, argn) {
  (void) args;
  (void) argn;

  lbm_block_ctx_from_extension();
  return ENC_SYM_NIL; //ignored
}

LBM_EXTENSION(ext_unblock, args, argn) {
  lbm_value res = ENC_SYM_EERROR;
  if (argn == 1 && lbm_is_number(args[0])) {
    lbm_cid c = lbm_dec_as_i32(args[0]);
    lbm_flat_value_t v;
    if (lbm_start_flatten(&v, 8)) {
      f_sym(&v, SYM_TRUE);
      lbm_finish_flatten(&v);
      lbm_unblock_ctx(c,&v);
      res = ENC_SYM_TRUE;
    }
  }
  return res;
}



static int override_calls=0, detach_calls=0;
static lbm_value fake_output(lbm_value *args,lbm_uint n){(void)args;(void)n;override_calls++;return ENC_SYM_TRUE;}
static lbm_value fake_detach(lbm_value *args,lbm_uint n){(void)args;(void)n;detach_calls++;return ENC_SYM_TRUE;}
static lbm_value host_print(lbm_value *args,lbm_uint n){
 char b[256]; for(lbm_uint i=0;i<n;i++){lbm_print_value(b,sizeof(b),args[i]);printf("PRINT %s\n",b);}fflush(stdout);return ENC_SYM_TRUE;
}
static lbm_value host_crc16(lbm_value *args,lbm_uint n){
 if((n!=1&&n!=2)||!lbm_is_array(args[0]))return ENC_SYM_TERROR;
 lbm_array_header_t *a=(lbm_array_header_t*)lbm_car(args[0]);
 if(a->elt_type!=LBM_TYPE_BYTE)return ENC_SYM_TERROR;
 unsigned int len=(n==2)?lbm_dec_as_u32(args[1]):a->size;
 if(len>a->size)len=a->size;
 uint16_t crc=0;uint8_t *data=a->data;
 for(unsigned int i=0;i<len;i++){crc^=(uint16_t)data[i]<<8;for(int b=0;b<8;b++)crc=(uint16_t)((crc&0x8000)?(crc<<1)^0x1021:crc<<1);}
 return lbm_enc_i(crc);
}
int main(int argc,char **argv){
 if(argc<2)return 2;
 unsigned int words=argc>2?(unsigned int)atoi(argv[2]):2048;
 lbm_uint *memory=calloc(words,sizeof(lbm_uint)),*bitmap=calloc(words/32,sizeof(lbm_uint));
 lbm_cons_t *heap=calloc(2464,sizeof(lbm_cons_t));
 if(!lbm_memory_init(memory,words,bitmap,words/32))return 3;
 lbm_print_init(print_stack_storage,PRINT_STACK_SIZE);lbm_symrepr_init();
 lbm_heap_init(heap,2464,gc_stack_storage,GC_STACK_SIZE);lbm_eval_init();lbm_init_env();lbm_eval_init_events(20);
 lbm_extensions_init(extension_storage,EXTENSION_STORAGE_SIZE);
 lbm_array_extensions_init();lbm_math_extensions_init();lbm_string_extensions_init();lbm_runtime_extensions_init(false);lbm_loop_extensions_init();
 lbm_add_extension("print",host_print);lbm_add_extension("crc16",host_crc16);
 lbm_add_extension("app-adc-override",fake_output);lbm_add_extension("app-adc-detach",fake_detach);
 lbm_set_dynamic_load_callback(dyn_load);lbm_set_timestamp_us_callback(timestamp_callback);lbm_set_usleep_callback(sleep_callback);lbm_set_printf_callback(printf);lbm_variables_init(variable_storage,VARIABLE_STORAGE_SIZE);lbm_set_verbose(true);lbm_set_ctx_done_callback(context_done_callback);
 lbm_uint padding=argc>3?(lbm_uint)atoi(argv[3]):0; if(padding&&!lbm_memory_allocate(padding))return 9;
 printf("PADDING_WORDS %llu\n",(unsigned long long)padding);
 printf("INIT words=%u bytes=%zu heap=2464 gcstack=160 printstack=128 free_words=%llu\n",words,(size_t)words*sizeof(lbm_uint),(unsigned long long)lbm_memory_num_free());
 pthread_t thread; if(pthread_create(&thread,NULL,eval_thd_wrapper,NULL))return 4;
 FILE *f=fopen(argv[1],"r"); if(!f)return 5;
 char *line=NULL;size_t cap=0;unsigned int count=0;
 while(getline(&line,&cap,f)>0){
  if(line[0]=='\n'||line[0]==';')continue;
  lbm_pause_eval_with_gc(20);while(lbm_get_eval_state()!=EVAL_CPS_STATE_PAUSED)sleep_callback(100);
  printf("STEP %u free_words=%llu free_cons=%llu\n",++count,(unsigned long long)lbm_memory_num_free(),(unsigned long long)lbm_heap_num_free());fflush(stdout);
  lbm_create_string_char_channel(&string_tok_state,&string_tok,line);experiment_done=false;
  lbm_cid cid=lbm_load_and_eval_expression(&string_tok);if(cid<0){fprintf(stderr,"load failed\n");return 6;}
  lbm_continue_eval();unsigned int wait=0;
  while(!experiment_done&&wait++<10000)sleep_callback(1000);
  if(!experiment_done||command_failed){fprintf(stderr,"failure or timeout step%u\n",count);return 7;}
 }
 lbm_pause_eval_with_gc(20);while(lbm_get_eval_state()!=EVAL_CPS_STATE_PAUSED)sleep_callback(100);
 printf("FINAL commands=%u free_words=%llu free_cons=%llu override_calls=%d detach_calls=%d\n",count,(unsigned long long)lbm_memory_num_free(),(unsigned long long)lbm_heap_num_free(),override_calls,detach_calls);
 return override_calls||detach_calls?8:0;
}
