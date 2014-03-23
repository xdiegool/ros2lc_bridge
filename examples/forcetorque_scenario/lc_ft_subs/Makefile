.PHONY: lc clean

LC_GEN_DIR=./src/lc_gen

lc:
	mkdir -p $(LC_GEN_DIR)
	touch  $(LC_GEN_DIR)/__init__.py
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/ft.py lc/ft.lc
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/proto.py /home/tommy/src/rws/ros2lc_bridge/generator/skel/lc/proto.lc

genbridge:
	# Make sure the ros node is running.
	rosrun generator generator.py -c conf.xml -f

sub_force:
	src/dumb_subscriber.py S__force_pt

sub_torque:
	src/dumb_subscriber.py S__torque_pt


clean:
	rm -fr $(LC_GEN_DIR)
