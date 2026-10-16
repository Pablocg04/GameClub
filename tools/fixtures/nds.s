.syntax unified
.arm
.global _start
_start:
    ldr r0, =0x04000304
    ldr r1, =0x8203
    strh r1, [r0]
    ldr r0, =0x04000240
    mov r1, #0x80
    strb r1, [r0]
    ldr r0, =0x04000000
    mov r1, #0x20000
    str r1, [r0]
poll:
    ldr r3, =0x02001000
    ldr r3, [r3]
    tst r3, #0x40
    ldreq r1, =0xfc00
    beq paint
    ldr r3, =0x04000130
    ldrh r3, [r3]
    tst r3, #1
    ldreq r1, =0x83e0
    ldrne r1, =0x801f
paint:
    ldr r0, =0x06800000
    mov r2, #0xc000
fill:
    strh r1, [r0], #2
    subs r2, r2, #1
    bne fill
    b poll
.ltorg
