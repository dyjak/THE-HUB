"use client";

import { TypeAnimation } from 'react-type-animation';

export default function TypedText({
                                      sequences = [],
                                      speed = 50,
                                      repeat = Infinity,
                                      className = ""
                                  }) {
    return (
        <TypeAnimation
            sequence={sequences}
            wrapper="span"
            speed={speed}
            style={{ fontSize: '2em', display: 'inline-block' }}
            repeat={repeat}
            className={className}
        />
    );
}