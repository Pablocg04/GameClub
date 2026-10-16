.syntax unified
.arm
.global _start
_start:
    ldr r0, =0x04000136
    ldr r1, =0x02001000
poll:
    ldrh r2, [r0]
    str r2, [r1]
    b poll
.ltorg
