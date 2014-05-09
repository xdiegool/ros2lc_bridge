BR:=$(shell rospack find service_bridge)
LABCOMMC=$(LABCOMM)/compiler/labComm.jar

all: lc

.PHONY: lc
lc:
	cp $(BR)/lc/*.lc lc/
	java -jar $(LABCOMMC) --python=src/lc_types.py lc/lc_types.lc
	java -jar $(LABCOMMC) --python=src/proto.py    lc/proto.lc
