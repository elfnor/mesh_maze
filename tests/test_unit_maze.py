

import mesh_maze.mesh_maze as mm
import bmesh
import bpy

import unittest

def put_to_scene(bm):
    if bpy.data.objects.get('Mesh') is not None:
        bpy.data.objects.remove(bpy.data.objects['Mesh'], do_unlink=True)

    bpy.ops.object.add(type='MESH')
    obj = bpy.context.object
    bm.to_mesh(obj.data)
    obj.data.update()


def make_edge_selection_grid(bm):
    """
    select a sparse grid on bm, where bm is a 10 x 10 grid
    """
    boundary_edges = set([
        e
        for e in bm.edges
        if (e.verts[0].is_boundary)
        or (e.verts[1].is_boundary)])
    sel_edges = set()
    for edge in bm.edges:
        if abs(edge.verts[0].co[1] - edge.verts[1].co[1]) < 0.001:
            sel_edges.add(edge)

        if (abs(round(edge.verts[0].co[0], 2)) in [0.78, 0.33]
                and abs(round(edge.verts[0].co[0], 2)) in [0.78, 0.33]):
            sel_edges.add(edge)
    sel_edges = sel_edges - boundary_edges
    for edge in sel_edges:
        edge.select = True
    return bm


class TestMeshMaze(unittest.TestCase):

    def test_module_available(self):
        self.assertTrue(mm.MAZE_PARAMS['maze_update'])

    def test_get_inner_edges_full_grid(self):
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=1.0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        for face in bm.faces:
            face.select = True

        sel_geom, inner_edges = mm.get_inner_edges(bm, 1)
        self.assertEqual(len(sel_geom), 361)
        self.assertEqual(len(inner_edges), 112)
        bm.free()

    def test_get_inner_edges_part_grid(self):
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=1.0)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        for face in bm.faces:
            if face.verts[0].co[1] > 0.0:
                face.select = True
            else:
                face.select = False

        sel_geom, inner_edges = mm.get_inner_edges(bm, 1)
        self.assertEqual(len(sel_geom), 50 + 85 + 36)
        self.assertEqual(len(inner_edges), 37)
        bm.free()

    def test_get_inner_edges_loops_grid(self):
        """
        select some edges that don't select full faces
        but could form a maze
        """
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=1.0)

        bm = make_edge_selection_grid(bm)

        sel_geom, inner_edges = mm.get_inner_edges(bm, 2)

        #put_to_scene(bm)

        self.assertEqual(len(sel_geom), 64 + 84)
        self.assertEqual(len(inner_edges), 84)
        bm.free()
        
    def test_type_offset_type(self):
        self.assertIsInstance(mm.MAZE_PARAMS['offset_type'], str)

    def test_generate_maze_full_grid(self):
        """
        generate full maze on 10 x 10 grid
        """
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=1.0)
        for face in bm.faces:
            face.select = True

        bm, maze_links, maze_verts = mm.generate_maze(bm, mm.MAZE_PARAMS)

        self.assertEqual(len(maze_links), 63)
        self.assertEqual(len(maze_verts), 64)
        # also count of selected faces should == 63+64
        self.assertEqual(sum(face.select for face in bm.faces), 127)
        bm.free()
        

    def test_generate_maze_loops_grid(self):
        """
        select some edges that don't select full faces
        but could form a maze
        """
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=10, y_segments=10, size=1.0)

        bm = make_edge_selection_grid(bm)
        nverts = sum(vert.select for vert in bm.verts)

        maze_params = mm.MAZE_PARAMS.copy()
        maze_params['boundary_type'] = 1
        maze_params['offset'] = 0.0
        bm, maze_links, maze_verts = mm.generate_maze(bm, maze_params)

        self.assertEqual(len(maze_links), 63)
        self.assertEqual(len(maze_verts), nverts)
        self.assertEqual(sum(edge.select for edge in bm.edges), len(maze_links))
        bm.free()

    def test_generate_maze_full_icosphere(self):
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=3, diameter=5.0)
        for face in bm.faces:
            face.select = True
        nverts = len(bm.verts)
        bm, maze_links, maze_verts = mm.generate_maze(bm, mm.MAZE_PARAMS)

        self.assertEqual(len(maze_links), 323 - nverts)
        self.assertEqual(len(maze_verts), nverts)
        self.assertEqual(sum(face.select for face in bm.faces), 323)
        bm.free()


if __name__ == "__main__":
    unittest.main(exit=False, verbosity=2)
