BR:=$(shell rospack find test_bridge)

FFPATH:=../../../../firefly
FF_BIN:=$(FFPATH)/build/
FF_INC:=$(FFPATH)/include/

LC_PATH:=../../../../labcomm
LC_BIN:=$(LC_PATH)/lib/c
LC_INC:=$(LC_PATH)/lib/c/

CC:=gcc
CFLAGS:=-Wall -Wextra -Werror \
       -Wno-unused-parameter -Wno-unused-variable \
       -Wno-unused-but-set-variable -Wno-unused-function \
       -std=gnu99 \
       -O3 \
       -I $(FF_INC) -I $(LC_INC)

LDFLAGS:=-L $(FF_BIN) -L $(LC_BIN)
LDLIBS:=-ltransport-udp-posix -lfirefly-werr -llabcomm -lpthread -lrt

ALL:=pingpong

.PHONY: all
all: $(ALL)

.PHONY: clean
clean:
	$(RM) src/*.o
	$(RM) src/*.lc
	$(RM) $(ALL)

src/lc_types.h src/lc_types.c: $(BR)/lc/lc_types.lc
	cd src/ && java -jar $(LABCOMMC) -C $^

src/proto.h src/proto.c: $(BR)/lc/proto.lc
	cd src/ && java -jar $(LABCOMMC) -C $^

pingpong: src/pingpong.o src/proto.o src/lc_types.o
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LDLIBS)
