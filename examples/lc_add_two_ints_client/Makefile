BR:=$(shell rospack find service_bridge)
LABCOMMC=$(LABCOMM)/compiler/labComm.jar

.PHONY: lc build_bridge

all: lc

lc: build_bridge
	cp $(BR)/lc/lc_types.lc lc/
	java -jar $(LABCOMMC) --python=src/lc_types.py lc/lc_types.lc
	java -jar $(LABCOMMC) --python=src/proto.py    lc/proto.lc
	@echo
	@echo "\tAll good, now run bridge with 'rosrun service_bridge main'"
	@echo

build_bridge:
	rosrun generator generator.py --lang=python -c conf.xml -f
