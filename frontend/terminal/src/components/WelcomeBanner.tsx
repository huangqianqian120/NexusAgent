import React from 'react';
import {Box, Text} from 'ink';

import {useTheme} from '../theme/ThemeContext.js';

const VERSION = '0.1.0';

// prettier-ignore
const LOGO = [
	'██╗   ██╗ ██████╗ ██╗  ██╗██╗██╗   ██╗███████╗',
	'██║   ██║██╔═══██╗╚██╗██╔╝██║██║   ██║██╔════╝',
	'██║   ██║██║   ██║ ╚███╔╝ ██║██║   ██║█████╗  ',
	'╚██╗ ██╔╝██║   ██║ ██╔██╗ ██║╚██╗ ██╔╝██╔══╝  ',
	' ╚████╔╝ ╚██████╔╝██╔╝ ██╗██║ ╚████╔╝ ███████╗',
	'  ╚═══╝   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝',
];

export function WelcomeBanner(): React.JSX.Element {
	const {theme} = useTheme();

	return (
		<Box flexDirection="column" marginBottom={1}>
			<Box flexDirection="column" paddingX={0}>
				{LOGO.map((line, i) => (
					<Text key={i} color={theme.colors.primary} bold>{line}</Text>
				))}
				<Text> </Text>
				<Text>
					<Text dimColor> An AI-powered coding assistant</Text>
					<Text dimColor>{'  '}v{VERSION}</Text>
				</Text>
				<Text> </Text>
				<Text>
					<Text dimColor> </Text>
					<Text color={theme.colors.primary}>/help</Text>
					<Text dimColor> commands</Text>
					<Text dimColor>{'  '}|{'  '}</Text>
					<Text color={theme.colors.primary}>/model</Text>
					<Text dimColor> switch</Text>
					<Text dimColor>{'  '}|{'  '}</Text>
					<Text color={theme.colors.primary}>Ctrl+C</Text>
					<Text dimColor> exit</Text>
				</Text>
			</Box>
		</Box>
	);
}
