#include <stdlib.h>
#include <stdio.h>

void alloc_array(void **a, size_t size, size_t elem_size)
{
	*a = calloc(size, elem_size);
	printf("Allocated array of size %zu\n", size*elem_size);
}
