from ..models import ImgUrl
from ..common import success_return, false_return, submit_return


def operate(obj, imgs, action):
    if obj:
        for img in imgs:
            image = ImgUrl.query.get(img)
            if image:
                if image not in obj.images:
                    getattr(obj.images, action)(image)
            else:
                return false_return(message="图片不存在"), 400
        return success_return(message=f"<{obj.id}>增加图片成功")
    else:
        return false_return(message=f"<{obj.id}>不存在"), 400
