USER := $(shell whoami)
ROSWS=~/ros_ws
ifeq ($(USER),erik)
	ROSWS=~/src
endif

.PHONY: lc
lc:
	cp $(ROSWS)/test/lc/lc_types.lc lc/ # Generated stuff.
	java -jar $(LABCOMMC) --python=src/lc_types.py lc/lc_types.lc
	java -jar $(LABCOMMC) --python=src/proto.py    lc/proto.lc
