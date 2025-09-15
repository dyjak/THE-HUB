import React from 'react';

export interface TypedTextProps {
  sequences: (string | number)[];
  speed?: number;
  repeat?: number | Infinity;
  className?: string;
}

export default function TypedText(props: TypedTextProps): React.ReactElement;
