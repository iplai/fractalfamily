"""Subdivide a Bezier curve kepping original Shape."""
from dataclasses import dataclass
from itertools import chain

import bpy
from mathutils import Vector


def getSplineSegs(spline: bpy.types.Spline):
    pts = spline.bezier_points
    segs = [Segment(pts[i - 1].co, pts[i - 1].handle_right, pts[i].handle_left, pts[i].co) for i in range(1, len(pts))]
    if (spline.use_cyclic_u):
        segs.append(Segment(pts[-1].co, pts[-1].handle_right, pts[0].handle_left, pts[0].co))
    return segs


def subdivideSeg(origSeg: 'Segment', noSegs=1):
    if noSegs < 2:
        return [origSeg]

    segs = []
    oldT = 0.0

    for i in range(0, noSegs - 1):
        t = (i + 1) / noSegs
        seg = origSeg.partialSeg(oldT, t)
        segs.append(seg)
        oldT = t

    seg = origSeg.partialSeg(oldT, 1.0)
    segs.append(seg)

    return segs


def subdivideCurve(curve: bpy.types.Curve, noSegs=1):
    origSpline = curve.splines[0]
    isCyclic = origSpline.use_cyclic_u
    segs = getSplineSegs(origSpline)
    segs = list(chain.from_iterable(subdivideSeg(seg, noSegs) for seg in segs))

    bezierPtsInfo: list[list[Vector]] = []

    for i, seg in enumerate(segs):
        pt = seg.start
        handleRight = seg.ctrl1

        if (i == 0):
            if isCyclic:
                handleLeft = segs[-1].ctrl2
            else:
                handleLeft = pt
        else:
            handleLeft = prevSeg.ctrl2

        bezierPtsInfo.append([pt, handleLeft, handleRight])
        prevSeg = seg

    if isCyclic:
        bezierPtsInfo[-1][2] = seg.ctrl1
    else:
        bezierPtsInfo.append([prevSeg.end, prevSeg.ctrl2, prevSeg.end])

    spline = curve.splines.new('BEZIER')
    spline.use_cyclic_u = isCyclic
    spline.bezier_points.add(len(bezierPtsInfo) - 1)

    for i, newPoint in enumerate(bezierPtsInfo):
        spline.bezier_points[i].co = newPoint[0]
        spline.bezier_points[i].handle_left = newPoint[1]
        spline.bezier_points[i].handle_right = newPoint[2]
        spline.bezier_points[i].handle_right_type = 'FREE'

    curve.splines.remove(origSpline)


@dataclass
class Segment:
    start: Vector
    ctrl1: Vector
    ctrl2: Vector
    end: Vector

    # see https://stackoverflow.com/a/879213
    def partialSeg(self, t0=0.0, t1=1.0):
        pts = [self.start, self.ctrl1, self.ctrl2, self.end]

        if (t0 > t1):
            t0, t1 = t1, t0

        # Let's make at least the line segments of predictable length
        if (pts[0] == pts[1] and pts[2] == pts[3]):
            pt0 = Vector([(1 - t0) * pts[0][i] + t0 * pts[2][i] for i in range(0, 3)])
            pt1 = Vector([(1 - t1) * pts[0][i] + t1 * pts[2][i] for i in range(0, 3)])
            return Segment(pt0, pt0, pt1, pt1)

        u0 = 1.0 - t0
        u1 = 1.0 - t1

        qa = [pts[0][i] * u0 * u0 + pts[1][i] * 2 * t0 * u0 + pts[2][i] * t0 * t0 for i in range(0, 3)]
        qb = [pts[0][i] * u1 * u1 + pts[1][i] * 2 * t1 * u1 + pts[2][i] * t1 * t1 for i in range(0, 3)]
        qc = [pts[1][i] * u0 * u0 + pts[2][i] * 2 * t0 * u0 + pts[3][i] * t0 * t0 for i in range(0, 3)]
        qd = [pts[1][i] * u1 * u1 + pts[2][i] * 2 * t1 * u1 + pts[3][i] * t1 * t1 for i in range(0, 3)]

        pta = Vector([qa[i] * u0 + qc[i] * t0 for i in range(0, 3)])
        ptb = Vector([qa[i] * u1 + qc[i] * t1 for i in range(0, 3)])
        ptc = Vector([qb[i] * u0 + qd[i] * t0 for i in range(0, 3)])
        ptd = Vector([qb[i] * u1 + qd[i] * t1 for i in range(0, 3)])

        return Segment(pta, ptb, ptc, ptd)
