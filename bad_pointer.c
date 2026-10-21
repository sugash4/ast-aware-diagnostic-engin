/*
 * test_cases/bad_pointer.c
 * Demonstrates: void pointer dereference (GCC error)
 *
 * Expected error (GCC):
 *   bad_pointer.c:25:16: error: void value not ignored as it ought to be
 *
 * Compile with:
 *   python main.py gcc test_cases/bad_pointer.c -o /tmp/bad_pointer
 */

#include <stdio.h>
#include <stdlib.h>

/* Process a generic buffer — intentionally accepts void* */
void process_buffer(void *buf, int size) {
    int i;

    /* BUG: Dereferencing a void pointer is illegal in C.
     * The compiler cannot determine the size of the pointee type,
     * so arithmetic / dereference on void* is undefined behaviour.
     */
    for (i = 0; i < size; i++) {
        /* ERROR LINE: void pointer dereference */
        printf("byte %d = %d\n", i, *buf);   /* line 25 — triggers the error */
        buf++;                                 /* line 26 — also illegal in strict C */
    }
}

int main(void) {
    unsigned char data[4] = {0xDE, 0xAD, 0xBE, 0xEF};
    process_buffer(data, 4);
    return 0;
}
