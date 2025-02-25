import itertools
import math
import re
import enum
from mathutils import Matrix, Vector
from dataclasses import dataclass

SQRT_3_OVER_2 = 0.8660254037844386


class DOMAINS(enum.IntEnum):
    G = 0  # Gaussian integers
    E = 1  # Eisenstein integers


class ComplexInt:
    """Represents a complex integer in either G or E domain."""

    def __init__(self, a: int = 0, b: int = 0, domain: DOMAINS = DOMAINS.G):
        self.a = a
        self.b = b
        self.domain = domain

    def __add__(self, other: "ComplexInt") -> "ComplexInt":
        """Add two complex integers."""
        return ComplexInt(self.a + other.a, self.b + other.b, self.domain)

    def __repr__(self) -> str:
        return f"{self.domain.name}{self.a, self.b}"

    @property
    def coord(self):
        """Convert to coordinate vector based on domain."""
        if self.domain == DOMAINS.G:
            return Vector((self.a, self.b, 0))

        return Vector((self.a - self.b / 2, self.b * SQRT_3_OVER_2, 0))

    @property
    def norm(self) -> int:
        """Calculate the norm based on domain."""
        if self.domain == DOMAINS.E:
            return self.a * self.a - self.a * self.b + self.b * self.b
        return self.a * self.a + self.b * self.b


class E(ComplexInt):
    def __init__(self, a: int = 0, b: int = 0, domain=DOMAINS.E) -> None:
        super().__init__(a, b, domain)


def compare(a: float, b: float, epsilon=0.001):
    return abs(a - b) < epsilon


def cal_transform_matrix(points: list[Vector], should_reverse=False) -> Matrix:
    src_start, src_end, tgt_start, tgt_end = points
    src_dir = src_end - src_start
    tgt_dir = tgt_end - tgt_start

    scale_factor = tgt_dir.length / src_dir.length
    if should_reverse:
        rotation_matrix = Matrix.Rotation(math.pi, 4, (0, 0, 1))
        src_dir = -src_dir
    else:
        rotation_matrix = Matrix()
    if compare(src_dir.angle(tgt_dir), math.pi):
        rotation_matrix = Matrix.Rotation(math.pi, 4, (0, 0, 1))
    else:
        rotation_matrix = src_dir.rotation_difference(tgt_dir).to_matrix().to_4x4() @ rotation_matrix
    # rotation_matrix = Matrix.Rotation(src_dir.angle(tgt_dir), 4, (0, 0, 1)) @ rotation_matrix
    translation_matrix = Matrix.Translation(tgt_start - src_start)
    scale_matrix = Matrix.Scale(scale_factor, 4)

    return translation_matrix @ rotation_matrix @ scale_matrix


@dataclass
class GeneratorElement:
    integer: ComplexInt
    transform: tuple[int, int]


class Generator:
    """Manages fractal generator elements and their transformations"""

    def __init__(self, elements: list[GeneratorElement], name: str = "", gene: str = ""):
        self.elements = elements
        self.domain = self.elements[0].integer.domain
        self.integer = sum((elem.integer for elem in self.elements), ComplexInt(domain=self.domain))
        self.name = name
        self.gene = gene
        self.max_level = 1
        self._init_level_points()
        self._init_matrices()

    def __str__(self):
        text = f"# 家族: {self.integer} 范数: {self.integer.norm}\n"
        for elem in self.elements:
            text += f"  {str(elem.integer): <10}{elem.transform}\n"
        return text

    def _init_level_points(self):
        """Initialize the first two levels of points"""
        self.level_points = [
            [self.integer.coord],  # Level 0
            [i.coord for i in itertools.accumulate(elem.integer for elem in self.elements)]  # Level 1
        ]

    def _init_matrices(self):
        """Initialize transformation matrices list.

        For each generator element, calculate a transformation matrix that maps
        the basic unit (from origin to total vector) to the corresponding segment.
        The start/end points are determined by transform[0].
        """
        # Get all points from level 1
        points = self.level_points[1]
        # Base unit start and end points
        base_start = Vector()  # Origin
        base_end = self.integer.coord  # Total vector

        # Calculate transformation matrix for each generator element
        self.matrices = []
        for i, (point, elem) in enumerate(zip(points, self.elements)):
            # Current segment start and end points
            segment_start = Vector() if i == 0 else points[i - 1]
            segment_end = point

            # Determine mapping direction based on transform flag
            source_points = [base_start, base_end]
            target_points = [segment_start, segment_end]
            should_reverse = elem.transform[0]
            if should_reverse:
                target_points = target_points[::-1]

            # Calculate and store transformation matrix
            matrix = cal_transform_matrix(source_points + target_points, should_reverse)
            self.matrices.append(matrix)

    def update_level_points(self, level: int):
        """Update fractal point coordinates to specified level.

        Each new level's points are obtained by applying generator element transformations
        to the previous level's points. Each generator element transformation includes:
        1. Optional point sequence reversal (transform[0])
        2. Optional reflection about total vector (transform[1])
        3. Apply transformation matrix
        """
        if level <= self.max_level:
            return

        for i in range(self.max_level + 1, level + 1):
            new_points = []  # for convenience the origin point (0, 0) is ignored
            for elem, matrix in zip(self.elements, self.matrices):
                points = self.level_points[i - 1]
                if elem.transform[0]:
                    points = reversed([Vector()] + points[:-1])
                if elem.transform[1]:
                    reflection_dir = self.integer.coord
                    points = [-p.reflect(reflection_dir) for p in points]

                # Apply transformation matrix and add to new points list
                new_points.extend(matrix @ point for point in points)

            self.level_points.append(new_points)

        self.max_level = level


def get_initiator_matrices(points: list[Vector], generator: Generator, is_closed=False):
    matrices: list[Matrix] = []

    points = [p.copy() for p in points]

    # Add start point as end point for closed splines
    if is_closed:
        points.append(points[0])

    # Calculate transformation matrix for each segment
    for i in range(1, len(points)):
        # Current segment start and end points
        segment_start = points[i - 1]
        segment_end = points[i]

        # Calculate transformation matrix mapping basic unit to current segment
        matrix = cal_transform_matrix([
            Vector(),                 # Source start
            generator.integer.coord,  # Source end
            segment_start,            # Target start
            segment_end               # Target end
        ])
        matrices.append(matrix)

    return matrices


def parse_gene(gene: str) -> list[GeneratorElement]:
    """Parse a gene string into list of (ComplexInt, transform) pairs.

    Example:
        "G 1 0 0 0 0 1 1 0" ->
        [
            GeneratorElement(ComplexInt(1,0), (0,0)),
            GeneratorElement(ComplexInt(0,1), (1,0))
        ]
    """
    # Split domain and numbers
    domain_str, *number_strings = gene.split()
    domain = DOMAINS[domain_str]

    # Convert to integers
    numbers = [int(n) for n in number_strings]

    # Process in groups of 4 and create pairs
    elements = []
    for a, b, t1, t2 in zip(numbers[::4], numbers[1::4], numbers[2::4], numbers[3::4]):
        integer = ComplexInt(a, b, domain)
        transform = (t1, t2)
        elements.append(GeneratorElement(integer, transform))

    return elements
