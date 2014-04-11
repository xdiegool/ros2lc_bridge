USER := $(shell whoami)
ROSWS=~/ros_ws
ifeq ($(USER),erik)
	ROSWS=~/src
endif

.PHONY: lc build_bridge

all: lc

lc: build_bridge
	cp $(ROSWS)/service_bridge/lc/lc_types.lc lc/ && \
		make -C $(ROSWS)/service_bridge
	java -jar $(LABCOMMC) --python=src/lc_types.py lc/lc_types.lc
	java -jar $(LABCOMMC) --python=src/proto.py    lc/proto.lc
	@echo
	@echo "\tAll good, now run bridge with 'rosrun service_bridge main'"
	@echo

build_bridge:
	rosrun generator_c generator.py -c conf.xml
