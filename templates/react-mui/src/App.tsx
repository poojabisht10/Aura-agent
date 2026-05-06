import { ThemeProvider, createTheme, CssBaseline, Box } from '@mui/material';

const theme = createTheme({
  // Theme will be customized based on Figma design
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ minHeight: '100vh', bgcolor: 'white' }}>
        {/* Components will be added here */}
      </Box>
    </ThemeProvider>
  )
}

export default App
