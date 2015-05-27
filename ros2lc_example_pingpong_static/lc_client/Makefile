LABCOMMC=$(LABCOMM)/compiler/labComm.jar
PKG=$(shell rospack find static_bridge)

clean:
	$(RM) src/*.pyc
	$(RM) lc/*
	$(RM) src/lc_types.py

.PHONY: lc
lc:
	cp $(PKG)/lc/* lc/
	java -jar $(LABCOMMC) --python=src/lc_types.py $(PKG)/lc/lc_types.lc
