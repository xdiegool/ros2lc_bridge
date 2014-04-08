USER := $(shell whoami)
ROSWS=~/ros_ws
ifeq ($(USER),erik)
	ROSWS=~/src
endif

.PHONY: lc build_bridge

all: lc

lc: build_bridge
	cp $(ROSWS)/test_bridge/lc/lc_types.lc lc/ # Generated stuff.
	java -jar $(LABCOMMC) --python=src/lc_types.py lc/lc_types.lc
	java -jar $(LABCOMMC) --python=src/proto.py    lc/proto.lc

build_bridge:
	rosrun generator generator.py -c conf.xml
