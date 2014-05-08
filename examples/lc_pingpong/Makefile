USER := $(shell whoami)
ROSWS=~/ros_ws
ifeq ($(USER),erik)
	ROSWS=~/src
endif

LABCOMMC=$(LABCOMM)/compiler/labComm.jar

.PHONY: lc
lc:
	cp $(ROSWS)/test_bridge/lc/lc_types.lc lc/ # Generated stuff.
	java -jar $(LABCOMMC) --python=src/lc_types.py lc/lc_types.lc
	java -jar $(LABCOMMC) --python=src/proto.py    lc/proto.lc
