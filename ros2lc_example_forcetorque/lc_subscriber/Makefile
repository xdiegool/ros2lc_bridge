PKG=$(shell rospack find ft_bridge)
LABCOMMC=$(LABCOMM)/compiler/labComm.jar

.PHONY: lc
lc:
	java -jar $(LABCOMMC) --python=src/ft.py $(PKG)/lc/ft.lc
	java -jar $(LABCOMMC) --python=src/proto.py $(PKG)/lc/proto.lc

.PHONY: genbridge
genbridge:
	# Make sure the ros node is running.
	rosrun generator_c generator.py -c conf.xml -f

.PHONY: sub_force
sub_force:
	src/dumb_subscriber.py /force_pt

.PHONY: sub_torque
sub_torque:
	src/dumb_subscriber.py /torque_pt

.PHONY: clean
clean:
	rm -fr $(LC_GEN_DIR)
