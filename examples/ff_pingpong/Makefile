BR:=$(shell rospack find test_bridge)

FF_BIN:=$(FIREFLY)/build/
FF_INC:=$(FIREFLY)/include/

LC_BIN:=$(LABCOMM)/lib/c
LC_INC:=$(LABCOMM)/lib/c/

CC:=gcc
CFLAGS:=-Wall -Wextra -Werror \
       -Wno-unused-parameter -Wno-unused-variable \
       -Wno-unused-but-set-variable -Wno-unused-function \
       -std=gnu99 \
       -O3 \
       -I $(FF_INC) -I $(LC_INC)

LDFLAGS:=-L $(FF_BIN) -L $(LC_BIN)
LDLIBS:=-ltransport-udp-posix -lfirefly-werr -lpthread -lrt

ALL:=pingpong

.PHONY: all
all: check-firefly check-labcomm $(ALL)

.PHONY: clean
clean:
	$(RM) src/*.o
	$(RM) src/*.lc
	$(RM) $(ALL)

src/lc_types.h src/lc_types.c: $(BR)/lc/lc_types.lc
	cd src/ && java -jar $(LABCOMMC) -C $^

src/proto.h src/proto.c: $(BR)/lc/proto.lc
	cd src/ && java -jar $(LABCOMMC) -C $^

pingpong: src/proto.o src/lc_types.o src/pingpong.o
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(LC_BIN)/liblabcomm.a $(LDLIBS)

.PHONY: check-firefly
check-firefly:
ifndef FIREFLY
    $(error FIREFLY is undefined)
endif

.PHONY: check-labcomm
check-labcomm:
ifndef LABCOMM
    $(error LABCOMM is undefined)
endif
