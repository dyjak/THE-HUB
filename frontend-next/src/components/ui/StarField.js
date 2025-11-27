import React, { Component } from 'react'

import StarfieldAnimation from 'react-starfield'

export default class Starfield extends Component {
    render() {
        return (
            <div
                aria-hidden
                style={{
                    position: 'fixed',
                    inset: 0,
                    width: '100%',
                    height: '100%',
                    zIndex: 0,
                    background: 'linear-gradient(to bottom right, #1f247dff rgba(49, 37, 95, 1)38)',
                    overflow: 'hidden',
                    pointerEvents: 'none'
                }}
            >
                <StarfieldAnimation
                    style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%'
                    }}
                />
            </div>
        )
    }
}