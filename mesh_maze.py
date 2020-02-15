# -*- coding: utf-8 -*-
"""
Created on Wed Jun 21 20:28:00 2017

@author: elfnor

maze mesh mod
should be standalone and able to run with a profiler or against unit tests

"""

import random
import bmesh
import mathutils

MAZE_PARAMS = {}
MAZE_PARAMS['maze_update'] = True
MAZE_PARAMS['rseed'] = 0
MAZE_PARAMS['link_centers'] = []
MAZE_PARAMS['vert_centers'] = []
MAZE_PARAMS['offset'] = 0.1
MAZE_PARAMS['offset_type'] = "OFFSET"
MAZE_PARAMS['use_loop_slide'] = True
MAZE_PARAMS['use_clamp_overlap'] = False
MAZE_PARAMS['boundary_type'] = 1
MAZE_PARAMS['depth'] = 0.1
MAZE_PARAMS['thickness'] = 0.0
MAZE_PARAMS['use_even_offset'] = False
MAZE_PARAMS['use_outset'] = False
MAZE_PARAMS['use_relative_offset'] = False
MAZE_PARAMS['braid'] = 0.0


def generate_maze(bm, maze_params):
    """
    generate the maze on the bm bmesh
    """
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    sel_geom, inner_edges = get_inner_edges(bm, maze_params['boundary_type'])
    if maze_params['maze_update']:
        all_edges = sorted(bm.edges, key=lambda edge: edge.index)
        full_mesh = inner_edges == all_edges
        random.seed(maze_params['rseed'])
        maze_path, maze_verts = recursive_back_tracker_maze(inner_edges, full_mesh)
        if maze_params['braid'] > 0.0:
            maze_path = do_braid(maze_path, maze_verts, maze_params['braid'])

        link_centers, vert_centers = get_maze_centers(maze_path, maze_verts)
    else:
        link_centers = maze_params['link_centers']
        vert_centers = maze_params['vert_centers']

    bevel_extrude(bm, sel_geom, maze_params, link_centers, vert_centers)
    return bm, link_centers, vert_centers


def get_inner_edges(bm, boundary_type):
    """get the edges to run maze on
    ignore the outer edge of selection and any edges with any verts on boundary
    input:
        bm: the bmesh for the whole mesh
    output:
        sel_geom: list of selected verts, edges, faces
        inner_edges: list of BMEdge
    """
    # get selection
    sel_verts = [v for v in bm.verts if v.select]
    sel_edges = [e for e in bm.edges if e.select]
    sel_faces = [f for f in bm.faces if f.select]
    sel_geom = sel_verts + sel_edges + sel_faces

    border_geom = bmesh.ops.region_extend(
        bm, geom=sel_geom,
        use_faces=False,
        use_face_step=True,
        use_contract=True)

    border_edges = [e for e in border_geom['geom']
                    if isinstance(e, bmesh.types.BMEdge)]

    boundary_edges = [e for e in sel_edges
                      if (e.verts[0].is_boundary)
                      or (e.verts[1].is_boundary)]

    outer_edges = set(border_edges + boundary_edges)

    inner_edges = list(set(sel_edges) - outer_edges)
    # need to sort the list of edges on index so the same maze
    # gets regenerated for the same value of rseed
    # profile shows this is not comapritively expensive even for large meshes
    inner_edges.sort(key=lambda edge: edge.index)
    if boundary_type == 2 or len(inner_edges) == 0:
        inner_edges = sorted(sel_edges, key=lambda edge: edge.index)
    return sel_geom, inner_edges


def recursive_back_tracker_maze(bm_edges, full_mesh=False):
    """trace a perfect maze through bm_edges
    input:
        bm_edges: list of BMEdges - needs to be pre-sorted on index
        full_mesh: does bm_edges include the whole mesh
    output:
        maze_path: list of BMEdges
        maze_verts: list of BMVerts
    """
    stack = []
    maze_path = []
    maze_verts = []
    # start at a random vert in maze
    start_vert = random.choice(bm_edges).verts[0]
    stack.append(start_vert)
    maze_verts.append(start_vert)
    while len(stack) > 0:
        current_vert = stack[-1]
        if full_mesh:
            # faster if we don't check edge is in bm_edges
            free_link_edges = [
                e
                for e in current_vert.link_edges
                if (e.other_vert(current_vert) not in maze_verts)
            ]
        else:
            # check edge in bm_edge
            free_link_edges = [
                e
                for e in current_vert.link_edges
                if (e in bm_edges)
                and (e.other_vert(current_vert) not in maze_verts)
            ]

        if len(free_link_edges) == 0:
            stack.pop()
        else:
            link_edge = random.choice(free_link_edges)
            maze_path.append(link_edge)
            new_vert = link_edge.other_vert(current_vert)
            stack.append(new_vert)
            maze_verts.append(new_vert)

    return maze_path, maze_verts


def get_maze_centers(maze_path, maze_verts):
    """find the centre of each edge in maze_path and the co-ordinates of the
    maze verts - these will be matched to face after the selection is bevelled
    input:
        maze_path: list of BMEDges that form the links in the maze
    output:
        link_centers: list of (x, y, z) cordinates of link centers
        vert_centers: list of (x, y, z) cordinates of vert centers
    """
    # find centre of each edge in maze_path
    link_centers = []

    for edge in maze_path:
        x_co, y_co, z_co = zip(*[edge.verts[poi].co for poi in [0, 1]])
        x_av, y_av, z_av = sum(x_co)/len(x_co), sum(y_co)/len(y_co), sum(z_co)/len(z_co)
        link_centers.append((x_av, y_av, z_av))

    maze_verts_co = [list(v.co) for v in maze_verts]
    return link_centers, maze_verts_co


def bevel_extrude(bm, sel_geom, maze_params, link_centers, vert_centers):
    """
    perform the bevel and extrude on the selected geometry
    select the maze path
    """
    for geom in sel_geom:
        geom.select = False

    if abs(maze_params['offset']) > 0.001:
        # bevel the whole mesh selection
        bevel_faces = bmesh.ops.bevel(
            bm,
            geom=sel_geom,
            offset=maze_params['offset'],
            offset_type=maze_params['offset_type'],
            segments=1,
            profile=0.5, vertex_only=0,
            loop_slide=maze_params['use_loop_slide'],
            clamp_overlap=maze_params['use_clamp_overlap'],
            material=-1)

        path_faces, wall_faces = get_maze_faces(bm, bevel_faces['faces'],
                                                link_centers + vert_centers,
                                                maze_params['boundary_type'])
        for face in path_faces:
            face.select = True

        if abs(maze_params['depth']) > 0.001:
            bmesh.ops.inset_region(
                bm,
                faces=wall_faces,
                thickness=maze_params['thickness'],
                depth=maze_params['depth'],
                use_boundary=True,
                use_even_offset=maze_params['use_even_offset'],
                use_outset=maze_params['use_outset'],
                use_relative_offset=maze_params['use_relative_offset'])

    else:
        path_edges = get_near_edges(bm, link_centers)
        for edge in path_edges:
            edge.select = True


def get_maze_faces(bm, bevel_faces, maze_centers, boundary_type):
    """find which of the faces in bm  are in the path and which are in the wall
    inputs:
        bm: the bmesh for the whole mesh
        bevel_faces: list of new faces crated by bevel operator
        maze_centers: list of (x, y, z) cordinates of link centers and verts
        boundary_type: see MESH_OT_maze_mesh.wall_types.
    ouputs:
        path_faces: list of faces that make up the path
        wall_faces: list of faces that make up the wall
    """
    # find center of each face in new bevel mesh faces
    face_centers = [f.calc_center_median() for f in bevel_faces]
    fc_tree = mathutils.kdtree.KDTree(len(face_centers))
    for i, center in enumerate(face_centers):
        fc_tree.insert(center, i)
    fc_tree.balance()
    path_face_ids = [fc_tree.find(v)[1] for v in maze_centers]
    path_faces = list({bevel_faces[id] for id in path_face_ids})

    # the selection of differnt boundary wall types works
    # but code seems clumsy
    wall_geom = bmesh.ops.region_extend(
        bm, geom=path_faces,
        use_faces=True,
        use_face_step=True,
        use_contract=False)

    thin_wall = wall_geom['geom']
    if boundary_type == 1:
        wall_faces = thin_wall
    elif boundary_type == 0:
        wall_faces = set(bevel_faces + thin_wall) - set(path_faces)
    elif boundary_type == 2:
        test_geom = bmesh.ops.region_extend(
            bm,
            geom=thin_wall + path_faces,
            use_faces=True,
            use_face_step=True,
            use_contract=True)

        boundary_faces = [
            f
            for f in thin_wall
            for v in f.verts
            if v.is_boundary
        ]
        wall_faces = (set(thin_wall)
                      - set(test_geom['geom'])
                      - set(boundary_faces))

    return path_faces, list(wall_faces)


def get_near_edges(bm, centers):
    """
    finds the edges in bm nearest to centers
    inputs:
        bm: the bmesh for the whole mesh
        centers: list of (x, y, z) cordinates of link centers
    output:
        list of BMEdges
    this is used if offset == 0 to only select edges
    it needs to be done this way so execute dosen't have to recreate maze_path
    on every parameter change - should be faster
    """
    # find center of each edge in bm
    bm.edges.ensure_lookup_table()
    bm_edge_centers = []
    for edge in bm.edges:
        x_co, y_co, z_co = zip(*[edge.verts[poi].co for poi in [0, 1]])
        x_av, y_av, z_av = sum(x_co)/len(x_co), sum(y_co)/len(y_co), sum(z_co)/len(z_co)
        bm_edge_centers.append((x_av, y_av, z_av))

    ec_tree = mathutils.kdtree.KDTree(len(bm_edge_centers))
    for i, center in enumerate(bm_edge_centers):
        ec_tree.insert(center, i)
    ec_tree.balance()
    path_edge_ids = [ec_tree.find(e)[1] for e in centers]
    path_edges = list({bm.edges[id] for id in path_edge_ids})
    return path_edges


def do_braid(maze_path, maze_verts, braid_amount=1.0):
    """
    Add links between dead ends (only one neighbour) and a neighbouring vertex
    p is the proportion (approx) of dead ends that are culled. Default p=1.0 removes
    them all.
    Linking dead ends produces loops in the maze.
    Prefer to link to another dead end if possible
    """
    # find all the verts that only have one neighbor in **maze**
    ends = [vert
            for vert in maze_verts
            if len(maze_nghbrs(vert, maze_path)) == 1]
    random.shuffle(ends)
    braid_links = maze_path[:]
    for vert in ends:
        vert_neghbrs = maze_nghbrs(vert, braid_links)
        if len(vert_neghbrs) == 1 and (random.random() < braid_amount):
            # its still a dead end, ignore some if p < 1
            # find edges not linked to vert by maze_path but linked by mesh
            unlinked = [edge
                        for edge in vert.link_edges
                        if edge not in maze_path and edge.other_vert(vert) in maze_verts]
            # find unlinked neighbours that are also dead ends
            best = [edge
                    for edge in unlinked
                    if len(maze_nghbrs(edge.other_vert(vert), braid_links)) == 1]

            if len(best) == 0:
                best = unlinked
            edge = random.choice(best)
            braid_links.append(edge)

    return braid_links


def maze_nghbrs(vert, maze_path):
    """ for vert find all neighbouring verts that are connected by
    an edge in maze_path"""

    nghbrs = [link_edge.other_vert(vert)
              for link_edge in vert.link_edges
              if link_edge in maze_path]
    return nghbrs
