import { ChakraProvider, Box } from '@chakra-ui/react';

function App() {
  return (
    <ChakraProvider>
      <Box minH="100vh" bg="white">
        {/* Components will be added here */}
      </Box>
    </ChakraProvider>
  )
}

export default App
