def test_ros_adapter_references_resolve():
    """Catch missing imports in lazily-executed ROS code paths."""
    import ast
    import builtins
    from pathlib import Path

    import turtlebot3_muse.ros_adapter as mod

    tree = ast.parse(Path(mod.__file__).read_text())
    local = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    local |= {a.arg for n in ast.walk(tree) if isinstance(n, ast.arguments)
              for a in n.args + n.kwonlyargs + [x for x in (n.vararg, n.kwarg) if x]}
    local |= {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    local |= {al.asname or al.name.split(".")[0] for n in ast.walk(tree)
              if isinstance(n, (ast.Import, ast.ImportFrom)) for al in n.names}
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    unresolved = used - local - set(vars(mod)) - set(dir(builtins))
    assert unresolved == set()
