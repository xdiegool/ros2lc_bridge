.PHONY: lc clean genbridge

LC_GEN_DIR=./src/lc_gen

# Here we use the protocol def. from the generators skel directory.
# In reality one should use the one from the generated code.
lc:
	mkdir -p $(LC_GEN_DIR)
	touch  $(LC_GEN_DIR)/__init__.py
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/pos_vel.py lc/pos_vel.lc
	java -jar $(LABCOMMC) --python=$(LC_GEN_DIR)/proto.py ../../../generator/skel/lc/proto.lc


clean:
	rm -fr $(LC_GEN_DIR)

genbridge:
	rosrun generator generator.py -c conf.xml --force
