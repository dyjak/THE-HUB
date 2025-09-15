"use client";
import { TypeAnimation } from 'react-type-animation';
import React from 'react';

export interface TypedTextProps {
  sequences: (string | number)[];
  speed?: number;
  repeat?: number;
  className?: string;
}

export default function TypedText({
  sequences,
  speed = 50,
  repeat = Infinity as unknown as number,
  className = ""
}: TypedTextProps) {
  return (
    <TypeAnimation
      sequence={sequences as any}
      wrapper="span"
      speed={speed as any}
      style={{ fontSize: '2em', display: 'inline-block' }}
      repeat={repeat as any}
      className={className}
    />
  );
}
