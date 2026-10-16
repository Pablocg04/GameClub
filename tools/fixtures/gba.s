.syntax unified
.arm
.global _start
_start:
    ldr r0, =0x04000000
    ldr r1, =0x0403
    strh r1, [r0]
poll:
    ldr r3, =0x04000130
    ldrh r3, [r3]
    tst r3, #1
    ldreq r1, =0x03e0
    ldrne r1, =0x001f
    ldr r0, =0x06000000
    ldr r2, =38400
fill:
    strh r1, [r0], #2
    subs r2, r2, #1
    bne fill
    b poll
.ltorg
