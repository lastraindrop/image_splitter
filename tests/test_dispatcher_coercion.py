# image_splitter/tests/test_dispatcher_coercion.py
import unittest
from PIL import Image
from image_splitter.engine.dispatcher import CommandDispatcher
from image_splitter.core import register_all_processors

class TestDispatcherCoercion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        register_all_processors()

    def test_dispatcher_injects_defaults(self):
        """Verify whether Dispatcher can inject default values for operators with omitted parameters."""
        img = Image.new("RGB", (100, 100))
        
        # grid_splitter() without parameters, default should be 3x3
        cmd = "grid_splitter()"
        results = CommandDispatcher.execute_chain(img, cmd)
        
        # 3x3 = 9 blocks
        self.assertEqual(len(results), 9)
        # 100 // 3 = 33
        self.assertEqual(results[0].width, 33)

    def test_dispatcher_coerces_types(self):
        """Verify whether Dispatcher can correctly convert string parameters to target types."""
        img = Image.new("RGB", (100, 100))
        
        # rows="2" (string) should be coerced to int
        cmd = "grid_splitter(rows='2', cols=2)"
        results = CommandDispatcher.execute_chain(img, cmd)
        
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].height, 50)

    def test_dispatcher_complex_chain(self):
        """Test type flow under complex chain calls."""
        img = Image.new("RGB", (100, 100))
        
        # Scale to 0.5 (50x50), then split into 2x2
        cmd = "resizer(width=0.5, height=0.5) | grid_splitter(rows=2, cols=2)"
        results = CommandDispatcher.execute_chain(img, cmd)
        
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0].size, (25, 25))

if __name__ == '__main__':
    unittest.main()
