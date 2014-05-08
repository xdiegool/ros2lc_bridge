.PHONY: lc clean genbridge

LC_GEN_DIR=./src/lc_gen
LABCOMMC:=$(LABCOMM)/compiler/labComm.jar
BRIDGE_DIR:=$(shell echo $$ROS_PACKAGE_PATH | cut -d":" -f1-1)

# Here we use the protocol def. from the generators skel directory.
# In reality one should use the one from the generated code.
lc:
	echo $(BRIDGE_DIR)
	mkdir -p $(LC_GEN_DIR)
	touch  $(LC_GEN_DIR)/__init__.py
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/pos_vel.py lc/pos_vel.lc
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/proto.py $(BRIDGE_DIR)/traj/lc/proto.lc


clean:
	rm -fr $(LC_GEN_DIR)

genbridge:
	rosrun generator generator.py -l python -c conf.xml --force
