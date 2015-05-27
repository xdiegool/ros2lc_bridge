LABCOMMC=$(LABCOMM)/compiler/labComm.jar
PKG=$(shell rospack find ext_service_bridge)

.PHONY: lc
lc:
	mkdir lc
	cp $(PKG)/lc/lc_types.lc lc/
	java -jar $(LABCOMMC) --python=src/lc_types.py $(PKG)/lc/lc_types.lc

clean:
	$(RM) -r lc
	$(RM)    src/lc_types.*

