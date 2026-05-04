# PyWebApp Native 🚀

**Lead Architect:** Sonu Vishwakarma (`sonuportfolio77@gmail.com`)

PyWebApp Native is a high-performance cross-platform framework. Build Android, Desktop, and Web applications using **Python** (for logic) and **React** (for UI).

## Installation

```bash
pip install pywebapp-native
```

## Quick Start

```bash
# Create a new project
pywebapp init MyApp
cd MyApp

# Launch development server
pywebapp dev

# Build for platforms
pywebapp build-android    # Generates Signed APK
pywebapp build-desktop    # Generates Windows EXE
pywebapp build-web        # Generates static web files
```

## For Developers

Add Python functions that are callable from JavaScript:

```python
# backend/handlers.py
from pywebapp.core import register, get_logger

logger = get_logger("handlers")

@register(description="Add two numbers")
def add(a, b):
    return a + b
```

Call them from React:

```jsx
import { call } from 'pywebapp-bridge';

const result = await call('add', [5, 7]);
// result = { success: true, result: 12 }
```

## License

Developed by **Sonu Vishwakarma**. (c) 2026. All rights reserved.
