import React from 'react';
import { View, ViewProps, StyleSheet } from 'react-native';

/**
 * Web-compatible SafeAreaView component
 * On web, this is just a regular View since there are no safe areas to handle
 */
export const SafeAreaView: React.FC<ViewProps & { className?: string }> = ({ style, className = '', ...props }) => {
    return (
        <View
            style={[
                {
                    flex: 1,
                    paddingTop: 'env(safe-area-inset-top, 0px)',
                    paddingBottom: 'env(safe-area-inset-bottom, 0px)',
                    paddingLeft: 'env(safe-area-inset-left, 0px)',
                    paddingRight: 'env(safe-area-inset-right, 0px)'
                } as any,
                style
            ]}
            // @ts-ignore
            className={`w-full h-full flex flex-col ${className}`}
            {...props}
        />
    );
};

export default SafeAreaView;
