.PHONY: lc clean genbridge

LC_GEN_DIR=./src/lc_gen
LABCOMMC:=$(LABCOMM)/compiler/labComm.jar
BRIDGE_DIR:=$(shell echo $$ROS_PACKAGE_PATH | cut -d":" -f1-1)
PKG=$(shell rospack find trajectory_bridge)

# Here we use the protocol def. from the generators skel directory.
# In reality one should use the one from the generated code.
lc:
	mkdir -p $(LC_GEN_DIR)
	touch  $(LC_GEN_DIR)/__init__.py
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/pos_vel.py $(PKG)/lc/pos_vel.lc
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/proto.py $(PKG)/lc/proto.lc


clean:
	rm -fr $(LC_GEN_DIR)

genbridge:
	rosrun ros2lc_generator generator.py -l python -c conf.xml --force
