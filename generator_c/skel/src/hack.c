#include <stdlib.h>

void alloc_array(void **a, size_t size, size_t elem_size)
{
	a = calloc(size, elem_size);
}
