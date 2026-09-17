from pydantic import BaseModel, Field, PositiveInt, model_validator


class CocoImage(BaseModel):
    id: int
    file_name: str
    width: PositiveInt
    height: PositiveInt


class CocoCategory(BaseModel):
    id: int
    name: str


class CocoAnnotation(BaseModel):
    id: int
    image_id: int
    category_id: int
    # COCO exige exactamente [x, y, width, height] — ni más ni menos.
    bbox: list[float] = Field(min_length=4, max_length=4)
    area: float = Field(ge=0)
    iscrowd: int = Field(ge=0, le=1)
    segmentation: list = Field(default_factory=list)


class CocoDataset(BaseModel):
    images: list[CocoImage]
    annotations: list[CocoAnnotation]
    categories: list[CocoCategory]

    @model_validator(mode="after")
    def check_referential_integrity(self) -> "CocoDataset":
        # Cada anotación debe apuntar a una imagen y una categoría que
        # realmente existan en el documento — nada de ids huérfanos.
        image_ids = {image.id for image in self.images}
        category_ids = {category.id for category in self.categories}

        for annotation in self.annotations:
            if annotation.image_id not in image_ids:
                raise ValueError(
                    f"annotation {annotation.id}: image_id {annotation.image_id} "
                    "does not exist in images"
                )
            if annotation.category_id not in category_ids:
                raise ValueError(
                    f"annotation {annotation.id}: category_id {annotation.category_id} "
                    "does not exist in categories"
                )

        return self
