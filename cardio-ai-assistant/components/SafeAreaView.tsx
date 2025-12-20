import React from 'react';
import { View, ViewProps } from 'react-native';

/**
 * Web-compatible SafeAreaView component
 * On web, this is just a regular View since there are no safe areas to handle
 */
export const SafeAreaView: React.FC<ViewProps> = ({ style, ...props }) => {
    return <View style={[{ flex: 1 }, style]} {...props} />;
};

export default SafeAreaView;
